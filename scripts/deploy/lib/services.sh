# systemd units, or a setsid fallback when systemd is not PID 1.

API_UNIT=/etc/systemd/system/voicestudio-api.service
WEB_UNIT=/etc/systemd/system/voicestudio-web.service
RUN_DIR=/run/voicestudio

write_api_unit() {
  local prefix=$1 uv_bin=$2
  cat >"$API_UNIT" <<EOF
[Unit]
Description=VoiceStudio API and web UI files
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${VOICESTUDIO_SERVICE_USER}
Group=${VOICESTUDIO_SERVICE_USER}
WorkingDirectory=${prefix}
EnvironmentFile=${VOICESTUDIO_ENV_FILE}
ExecStart=${uv_bin} run --no-sync uvicorn main:app --app-dir backend --host 127.0.0.1 --port \${OMNIVOICE_PORT} --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=on-failure
RestartSec=3
TimeoutStartSec=300
TimeoutStopSec=30
NoNewPrivileges=true
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF
}

write_web_unit() {
  local prefix=$1 mode=$2
  local exec_start
  case "$mode" in
    proxy)
      exec_start="/usr/bin/python3 ${prefix}/scripts/deploy/web_proxy.py"
      ;;
    caddy)
      exec_start="$(command -v caddy) run --config ${VOICESTUDIO_DEFAULT_ETC}/Caddyfile"
      ;;
    nginx)
      # nginx stays under its own package unit. This unit is a oneshot that
      # reloads it so install/update/uninstall have one name to restart.
      cat >"$WEB_UNIT" <<EOF
[Unit]
Description=VoiceStudio nginx reload
After=voicestudio-api.service nginx.service
Requires=voicestudio-api.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nginx -t
ExecStart=/bin/systemctl reload nginx.service
ExecStop=/bin/true

[Install]
WantedBy=multi-user.target
EOF
      return
      ;;
    *) die "Unknown web mode: $mode" ;;
  esac
  local extra=""
  if [ "$mode" = caddy ]; then
    extra=$(cat <<'EOF'
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
User=root
Group=root
EOF
)
  else
    extra=$(cat <<EOF
User=${VOICESTUDIO_SERVICE_USER}
Group=${VOICESTUDIO_SERVICE_USER}
NoNewPrivileges=true
EOF
)
  fi
  cat >"$WEB_UNIT" <<EOF
[Unit]
Description=VoiceStudio public web proxy
After=voicestudio-api.service
Requires=voicestudio-api.service

[Service]
Type=simple
${extra}
WorkingDirectory=${prefix}
EnvironmentFile=${VOICESTUDIO_ENV_FILE}
ExecStart=${exec_start}
Restart=on-failure
RestartSec=2
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF
}

install_units() {
  local prefix=$1 mode=$2
  local uv_bin
  uv_bin=$(command -v uv)
  [ -n "$uv_bin" ] || die "uv is not on PATH"
  write_api_unit "$prefix" "$uv_bin"
  write_web_unit "$prefix" "$mode"
  if systemd_running; then
    systemctl daemon-reload
    systemctl enable voicestudio-api.service voicestudio-web.service
  else
    log "Wrote ${API_UNIT} and ${WEB_UNIT}. systemd is not running, so they were not enabled."
  fi
}

wait_for_health() {
  local port=$1 tries=${2:-90}
  local i
  for i in $(seq 1 "$tries"); do
    if curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      log "API /health is ok"
      return 0
    fi
    sleep 2
  done
  die "API did not become healthy on 127.0.0.1:${port}. See /var/log/voicestudio/api.log or journalctl -u voicestudio-api"
}

start_services() {
  local no_systemd=$1 api_port=$2
  if [ "$no_systemd" != 1 ] && systemd_running; then
    systemctl restart voicestudio-api.service
    wait_for_health "$api_port"
    systemctl restart voicestudio-web.service
    return
  fi
  if [ "$no_systemd" != 1 ]; then
    die "systemd is installed but not running (this is not a normal VPS). Re-run with --no-systemd to start the processes in the background, or boot a host where systemd is PID 1."
  fi
  log "Starting the API and web proxy without systemd"
  install -d -o "$VOICESTUDIO_SERVICE_USER" -g "$VOICESTUDIO_SERVICE_USER" -m 0755 "$RUN_DIR"
  stop_background || true
  local uv_bin prefix
  uv_bin=$(command -v uv)
  prefix=$(env_get VOICESTUDIO_PREFIX)
  [ -n "$prefix" ] || die "VOICESTUDIO_PREFIX is missing from the env file"
  setsid runuser -u "$VOICESTUDIO_SERVICE_USER" -- \
    bash -c 'echo $$ > /run/voicestudio/api.pid; set -a; . /etc/voicestudio/voicestudio.env; set +a; cd "$VOICESTUDIO_PREFIX"; exec "$1" run --no-sync uvicorn main:app --app-dir backend --host 127.0.0.1 --port "$OMNIVOICE_PORT" --proxy-headers --forwarded-allow-ips=127.0.0.1 >>/var/log/voicestudio/api.log 2>&1' \
    bash "$uv_bin" </dev/null &
  wait_for_health "$api_port"
  local mode
  mode=$(env_get VOICESTUDIO_WEB_MODE)
  [ -n "$mode" ] || mode=proxy
  case "$mode" in
    caddy)
      setsid runuser -u root -- bash -c 'echo $$ > /run/voicestudio/web.pid; exec caddy run --config /etc/voicestudio/Caddyfile >>/var/log/voicestudio/web.log 2>&1' </dev/null &
      ;;
    nginx)
      nginx -t
      systemctl reload nginx.service 2>/dev/null || nginx -s reload || nginx
      ;;
    *)
      setsid runuser -u "$VOICESTUDIO_SERVICE_USER" -- \
        bash -c 'echo $$ > /run/voicestudio/web.pid; set -a; . /etc/voicestudio/voicestudio.env; set +a; exec /usr/bin/python3 "$VOICESTUDIO_PREFIX/scripts/deploy/web_proxy.py" >>/var/log/voicestudio/web.log 2>&1' \
        </dev/null &
      ;;
  esac
}

stop_background() {
  local name pid
  for name in api web; do
    if [ -f "${RUN_DIR}/${name}.pid" ]; then
      pid=$(cat "${RUN_DIR}/${name}.pid" 2>/dev/null || true)
      if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
      fi
      rm -f "${RUN_DIR}/${name}.pid"
    fi
  done
}

stop_services() {
  if systemd_running; then
    systemctl disable --now voicestudio-web.service voicestudio-api.service >/dev/null 2>&1 || true
    rm -f "$API_UNIT" "$WEB_UNIT"
    systemctl daemon-reload || true
  else
    stop_background || true
    rm -f "$API_UNIT" "$WEB_UNIT"
  fi
}

public_url() {
  local domain=$1 port=$2
  if [ -n "$domain" ]; then
    printf 'https://%s' "$domain"
    return
  fi
  local ip
  ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  if [ -z "$ip" ]; then
    ip=127.0.0.1
  fi
  printf 'http://%s:%s' "$ip" "$port"
}

print_summary() {
  local url=$1 key_new=$2 web_port=$3 api_port=$4 domain=$5
  cat <<EOF

VoiceStudio is up.
  Web UI:  ${url}
  API:     same origin (loopback only on 127.0.0.1:${api_port})
  Env:     ${VOICESTUDIO_ENV_FILE}
EOF
  if [ "$key_new" = 1 ]; then
    printf '  API key: %s\n' "$(env_get OMNIVOICE_API_KEY)"
    printf '  The browser asks for this key once and exchanges it for a session.\n'
  else
    printf '  API key: unchanged (see %s)\n' "$VOICESTUDIO_ENV_FILE"
  fi
  cat <<EOF

Open the firewall for the public port only. Leave ${api_port} closed.
EOF
  if [ -n "$domain" ]; then
    cat <<EOF
  sudo ufw allow OpenSSH
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
EOF
  else
    cat <<EOF
  sudo ufw allow OpenSSH
  sudo ufw allow ${web_port}/tcp
EOF
  fi
  cat <<EOF
  sudo ufw enable

The first browser session opens a setup wizard. Speech needs the
k2-fsa/OmniVoice weights (about 2.4 GB) from Hugging Face. The app asks
before it downloads them. No API key is required for that public model.
EOF
}

maybe_firewall() {
  local enabled=$1 port=$2 domain=$3
  [ "$enabled" = 1 ] || return 0
  command -v ufw >/dev/null 2>&1 || die "--firewall needs ufw (apt-get install ufw)"
  ufw allow OpenSSH
  if [ -n "$domain" ]; then
    ufw allow 80/tcp
    ufw allow 443/tcp
  else
    ufw allow "${port}/tcp"
  fi
  ufw --force enable
  log "ufw enabled. Confirm a second SSH session still works."
}
