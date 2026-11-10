#!/usr/bin/env bash
# Root-owned service helper. Installed to /usr/local/lib/voicestudio/.
# The copy inside the git tree is not what sudo runs.
set -euo pipefail

ENV_FILE=${VOICESTUDIO_ENV_FILE:-/etc/voicestudio/voicestudio.env}
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

PREFIX=${VOICESTUDIO_PREFIX:-/opt/voicestudio}
API_PORT=${OMNIVOICE_PORT:-3900}
RUN_DIR=/run/voicestudio
UV=${UV_BIN:-/usr/local/bin/uv}

verb=${1:-status}
case "$verb" in
  status|restart|stop|update) ;;
  *) echo "usage: service-control.sh status|restart|stop|update" >&2; exit 2 ;;
esac

systemd_up() { [ -S /run/systemd/private ]; }

pid_alive() {
  local file=$1 pid
  [ -f "$file" ] || return 1
  pid=$(cat "$file" 2>/dev/null || true)
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

stop_pids() {
  local name file pid
  for name in web api; do
    file="$RUN_DIR/${name}.pid"
    if [ -f "$file" ]; then
      pid=$(cat "$file" 2>/dev/null || true)
      if [ -n "${pid:-}" ]; then
        kill "$pid" 2>/dev/null || true
      fi
      rm -f "$file"
    fi
  done
  sleep 0.4
}

start_pids() {
  install -d -o "${VOICESTUDIO_SERVICE_USER:-voicestudio}" -g "${VOICESTUDIO_SERVICE_USER:-voicestudio}" -m 0755 "$RUN_DIR"
  local user=${VOICESTUDIO_SERVICE_USER:-voicestudio}
  setsid runuser -u "$user" -- bash -c \
    'echo $$ > /run/voicestudio/api.pid; set -a; . /etc/voicestudio/voicestudio.env; set +a; cd "$VOICESTUDIO_PREFIX"; exec /usr/local/bin/uv run --no-sync uvicorn main:app --app-dir backend --host 127.0.0.1 --port "$OMNIVOICE_PORT" --proxy-headers --forwarded-allow-ips=127.0.0.1 >>/var/log/voicestudio/api.log 2>&1' \
    </dev/null &
  setsid runuser -u "$user" -- bash -c \
    'echo $$ > /run/voicestudio/web.pid; set -a; . /etc/voicestudio/voicestudio.env; set +a; exec /usr/bin/python3 "$VOICESTUDIO_PREFIX/scripts/deploy/web_proxy.py" >>/var/log/voicestudio/web.log 2>&1' \
    </dev/null &
}

case "$verb" in
  status)
    if systemd_up; then
      systemctl is-active voicestudio-api.service || true
      systemctl is-active voicestudio-web.service || true
    else
      if pid_alive "$RUN_DIR/api.pid"; then echo api running; else echo api stopped; fi
      if pid_alive "$RUN_DIR/web.pid"; then echo web running; else echo web stopped; fi
    fi
    ;;
  stop)
    if systemd_up; then
      systemctl stop voicestudio-web.service voicestudio-api.service
    else
      stop_pids
    fi
    ;;
  restart)
    if systemd_up; then
      systemctl restart voicestudio-api.service voicestudio-web.service
    else
      stop_pids
      start_pids
    fi
    ;;
  update)
    exec bash "$PREFIX/scripts/update.sh"
    ;;
esac
