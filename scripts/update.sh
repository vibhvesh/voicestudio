#!/usr/bin/env bash
# Pull the latest checkout, reinstall dependencies, rebuild the web UI, and
# restart VoiceStudio. The env file, database, and downloaded models stay put.
#
#   sudo bash /opt/voicestudio/scripts/update.sh
#
# Piped form, after a public clone already lives in /opt/voicestudio:
#   curl -fsSL https://cursor.com/codebase/vibhvesh-chandel/tmp-975794ea12dd953e/raw/main/scripts/update.sh | sudo bash
set -euo pipefail

if [ ! -f "${BASH_SOURCE[0]:-}" ]; then
  target=${VOICESTUDIO_PREFIX:-/opt/voicestudio}/scripts/update.sh
  [ -f "$target" ] || {
    printf 'voicestudio: %s is not installed. Run scripts/install.sh first.\n' "$target" >&2
    exit 1
  }
  exec bash "$target" "$@"
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=deploy/lib/common.sh
. "$SCRIPT_DIR/deploy/lib/common.sh"
# shellcheck source=deploy/lib/prereqs.sh
. "$SCRIPT_DIR/deploy/lib/prereqs.sh"
# shellcheck source=deploy/lib/app.sh
. "$SCRIPT_DIR/deploy/lib/app.sh"
# shellcheck source=deploy/lib/tls.sh
. "$SCRIPT_DIR/deploy/lib/tls.sh"
# shellcheck source=deploy/lib/services.sh
. "$SCRIPT_DIR/deploy/lib/services.sh"

NO_SYSTEMD=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-systemd) NO_SYSTEMD=1; shift ;;
    -h|--help)
      cat <<'EOF'
Usage: sudo bash scripts/update.sh [--no-systemd]

Pulls the git ref recorded at install time, reinstalls dependencies, rebuilds
the web UI, and restarts services. Does not rotate OMNIVOICE_API_KEY and does
not delete /var/lib/voicestudio.
EOF
      exit 0
      ;;
    *) die "Unknown option: $1" ;;
  esac
done

if [ "$(id -u)" -ne 0 ]; then
  exec sudo -E bash "$SCRIPT_DIR/update.sh" "$@"
fi
require_root
[ -f "$VOICESTUDIO_ENV_FILE" ] || die "Missing ${VOICESTUDIO_ENV_FILE}. Install first."
PREFIX=$(env_get VOICESTUDIO_PREFIX)
DATA=$(env_get OMNIVOICE_DATA_DIR)
REF=$(env_get VOICESTUDIO_REF)
REPO=$(env_get VOICESTUDIO_REPO)
API_PORT=$(env_get OMNIVOICE_PORT)
DOMAIN=$(env_get VOICESTUDIO_DOMAIN)
TLS=$(env_get VOICESTUDIO_TLS)
WEB_MODE=$(env_get VOICESTUDIO_WEB_MODE)
[ -n "$PREFIX" ] || die "VOICESTUDIO_PREFIX is empty"
[ -n "$DATA" ] || DATA=$VOICESTUDIO_DEFAULT_DATA
[ -n "$REF" ] || REF=$VOICESTUDIO_DEFAULT_REF
[ -n "$API_PORT" ] || API_PORT=$VOICESTUDIO_DEFAULT_API_PORT
[ -d "$PREFIX/.git" ] || die "$PREFIX has no .git directory. Re-run install.sh --source to refresh a copied tree."
is_our_tree "$PREFIX" || die "$PREFIX is not a VoiceStudio VPS install"

prereq_all
TORCH=$(detect_torch_variant)
previous=$(env_get OMNIVOICE_TORCH_VARIANT)
if [ -n "$previous" ] && [ "$previous" != "$TORCH" ]; then
  log "Compute changed (${previous} -> ${TORCH}). Dependencies will be reinstalled for the new wheels."
fi
env_set OMNIVOICE_TORCH_VARIANT "$TORCH"

log "Updating $PREFIX to origin/${REF}"
token=${VOICESTUDIO_GIT_TOKEN:-}
if [ -n "$token" ] && [ -n "$REPO" ]; then
  git -C "$PREFIX" -c "safe.directory=$PREFIX" remote set-url origin "$(repo_url_with_token "$REPO" "$token")"
fi
if ! git -C "$PREFIX" -c "safe.directory=$PREFIX" fetch origin "$REF"; then
  die "git fetch failed. A private repository needs a credential root can use (VOICESTUDIO_GIT_TOKEN or a root git credential). Models and config were not touched."
fi
git -C "$PREFIX" -c "safe.directory=$PREFIX" checkout -B "$REF" "origin/$REF"
git -C "$PREFIX" -c "safe.directory=$PREFIX" reset --hard "origin/$REF"
if [ -n "$REPO" ]; then
  git -C "$PREFIX" -c "safe.directory=$PREFIX" remote set-url origin "$REPO"
fi

install_app_deps "$PREFIX" "$TORCH"
python3 "$PREFIX/scripts/deploy/web_proxy.py" --self-test
if [ -n "$DOMAIN" ]; then
  write_tls_config "$DOMAIN" "${TLS:-caddy}" "$API_PORT" ""
fi
chown_tree "$PREFIX" "$DATA"
write_marker "$PREFIX"
install_units "$PREFIX" "${WEB_MODE:-proxy}"
start_services "$NO_SYSTEMD" "$API_PORT"
log "Update finished. API key and ${DATA} were kept."
log "Web UI: $(public_url "$DOMAIN" "$(env_get VOICESTUDIO_WEB_PORT)")"
