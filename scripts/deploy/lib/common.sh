# Shared paths, logging, and small helpers for the VPS scripts.
# Sourced, not executed.

: "${VOICESTUDIO_DEFAULT_PREFIX:=/opt/voicestudio}"
: "${VOICESTUDIO_DEFAULT_DATA:=/var/lib/voicestudio}"
: "${VOICESTUDIO_DEFAULT_ETC:=/etc/voicestudio}"
: "${VOICESTUDIO_DEFAULT_WEB_PORT:=8787}"
: "${VOICESTUDIO_DEFAULT_API_PORT:=3900}"
: "${VOICESTUDIO_DEFAULT_REPO:=https://origin.cursor.com/git/vibhvesh-chandel/tmp-975794ea12dd953e.git}"
: "${VOICESTUDIO_DEFAULT_REF:=main}"
VOICESTUDIO_RAW_BASE="https://cursor.com/codebase/vibhvesh-chandel/tmp-975794ea12dd953e/raw/main"
VOICESTUDIO_SERVICE_USER="voicestudio"
VOICESTUDIO_ENV_FILE="${VOICESTUDIO_DEFAULT_ETC}/voicestudio.env"

log() { printf 'voicestudio: %s\n' "$*"; }
die() { printf 'voicestudio: %s\n' "$*" >&2; exit 1; }

running_from_file() {
  local src="${BASH_SOURCE[1]:-${BASH_SOURCE[0]:-}}"
  # When this file is sourced, the caller's source is one frame up.
  # Callers pass their own path instead; see entry scripts.
  [ -n "$src" ] && [ -f "$src" ]
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    die "Run as root (sudo)."
  fi
}

require_debian() {
  if [ ! -f /etc/debian_version ]; then
    die "These scripts target Ubuntu/Debian. On another distribution install git, curl, ffmpeg, libsndfile, bun, and uv, then run again on a Debian-family host."
  fi
}

valid_port() {
  case "$1" in
    ''|*[!0-9]*) return 1 ;;
  esac
  [ "$1" -ge 1 ] && [ "$1" -le 65535 ]
}

# Absolute path that is not a filesystem root we must never delete.
safe_abs_dir() {
  local path=$1
  case "$path" in
    /*) ;;
    *) die "Path must be absolute: $path" ;;
  esac
  case "$path" in
    /|/usr|/bin|/sbin|/lib|/lib64|/boot|/home|/root|/etc|/var|/opt|/tmp|/usr/bin|/usr/local|/usr/local/bin)
      die "Refusing unsafe path: $path"
      ;;
  esac
}

systemd_running() {
  [ -S /run/systemd/private ] && command -v systemctl >/dev/null 2>&1
}

# cpu, or cuda when an NVIDIA driver answers.
detect_torch_variant() {
  if [ -e /proc/driver/nvidia/version ] || [ -e /dev/nvidiactl ] || command -v nvidia-smi >/dev/null 2>&1; then
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
      printf 'cuda'
      return
    fi
    if [ -e /proc/driver/nvidia/version ]; then
      printf 'cuda'
      return
    fi
  fi
  printf 'cpu'
}

env_get() {
  local key=$1
  [ -f "$VOICESTUDIO_ENV_FILE" ] || return 0
  awk -F= -v k="$key" 'index($0, k "=") == 1 { print substr($0, length(k) + 2); exit }' \
    "$VOICESTUDIO_ENV_FILE"
}

env_set() {
  local key=$1 value=$2
  local tmp dir
  dir=$(dirname "$VOICESTUDIO_ENV_FILE")
  mkdir -p "$dir"
  tmp=$(mktemp "${dir}/.env.XXXXXX")
  if [ -f "$VOICESTUDIO_ENV_FILE" ]; then
    grep -v "^${key}=" "$VOICESTUDIO_ENV_FILE" >"$tmp" || true
  fi
  printf '%s=%s\n' "$key" "$value" >>"$tmp"
  if getent group "$VOICESTUDIO_SERVICE_USER" >/dev/null 2>&1; then
    chown "root:${VOICESTUDIO_SERVICE_USER}" "$tmp"
    chmod 0640 "$tmp"
  else
    chmod 0600 "$tmp"
  fi
  mv "$tmp" "$VOICESTUDIO_ENV_FILE"
}

ensure_service_user() {
  local data=$1
  if ! getent group "$VOICESTUDIO_SERVICE_USER" >/dev/null 2>&1; then
    groupadd --system "$VOICESTUDIO_SERVICE_USER"
  fi
  if ! getent passwd "$VOICESTUDIO_SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --gid "$VOICESTUDIO_SERVICE_USER" \
      --home-dir "$data" --shell /usr/sbin/nologin \
      "$VOICESTUDIO_SERVICE_USER"
  fi
  install -d -o "$VOICESTUDIO_SERVICE_USER" -g "$VOICESTUDIO_SERVICE_USER" -m 0750 \
    "$data" "$data/huggingface" "$data/cache" /var/log/voicestudio
}

marker_path() {
  printf '%s/.voicestudio-vps' "$1"
}

write_marker() {
  local prefix=$1
  printf 'prefix=%s\ninstalled=%s\n' "$prefix" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$(marker_path "$prefix")"
}

is_our_tree() {
  local prefix=$1
  [ -f "$(marker_path "$prefix")" ] || [ -f "$prefix/scripts/deploy/web_proxy.py" ]
}
