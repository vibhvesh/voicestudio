#!/usr/bin/env bash
# Stop VoiceStudio and remove the app tree.
# Models and /etc/voicestudio are kept unless you confirm or pass --purge.
#
#   sudo bash /opt/voicestudio/scripts/uninstall.sh
#   sudo bash /opt/voicestudio/scripts/uninstall.sh --purge
#   sudo bash /opt/voicestudio/scripts/uninstall.sh --keep-data
set -euo pipefail

if [ ! -f "${BASH_SOURCE[0]:-}" ]; then
  target=${VOICESTUDIO_PREFIX:-/opt/voicestudio}/scripts/uninstall.sh
  [ -f "$target" ] || {
    printf 'voicestudio: %s is not installed\n' "$target" >&2
    exit 1
  }
  exec bash "$target" "$@"
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=deploy/lib/common.sh
. "$SCRIPT_DIR/deploy/lib/common.sh"
# shellcheck source=deploy/lib/services.sh
. "$SCRIPT_DIR/deploy/lib/services.sh"

PURGE=0
KEEP=0
NO_SYSTEMD=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --purge) PURGE=1; shift ;;
    --keep-data) KEEP=1; shift ;;
    --no-systemd) NO_SYSTEMD=1; shift ;;
    -h|--help)
      cat <<'EOF'
Usage: sudo bash scripts/uninstall.sh [--purge | --keep-data] [--no-systemd]

Stops the API and web services and deletes the app checkout.
Downloaded models and /etc/voicestudio are kept unless you pass --purge
or answer yes at the prompt. --keep-data never deletes them.
EOF
      exit 0
      ;;
    *) die "Unknown option: $1" ;;
  esac
done

if [ "$PURGE" = 1 ] && [ "$KEEP" = 1 ]; then
  die "--purge and --keep-data cannot be combined"
fi

if [ "$(id -u)" -ne 0 ]; then
  exec sudo -E bash "$SCRIPT_DIR/uninstall.sh" "$@"
fi
require_root

PREFIX=$(env_get VOICESTUDIO_PREFIX)
DATA=$(env_get OMNIVOICE_DATA_DIR)
[ -n "$PREFIX" ] || PREFIX=$VOICESTUDIO_DEFAULT_PREFIX
[ -n "$DATA" ] || DATA=$VOICESTUDIO_DEFAULT_DATA
safe_abs_dir "$PREFIX"
safe_abs_dir "$DATA"

if [ -d "$PREFIX" ] && ! is_our_tree "$PREFIX"; then
  die "$PREFIX exists but is not a VoiceStudio VPS tree. Refusing to delete it."
fi

log "Stopping services"
if [ "$NO_SYSTEMD" = 1 ] || ! systemd_running; then
  stop_background || true
  rm -f "$API_UNIT" "$WEB_UNIT"
else
  stop_services
fi

if [ -d "$PREFIX" ]; then
  log "Removing $PREFIX"
  rm -rf "$PREFIX"
fi

rm -f /etc/nginx/sites-enabled/voicestudio /etc/nginx/sites-available/voicestudio
rm -f "${VOICESTUDIO_DEFAULT_ETC}/Caddyfile"
if command -v nginx >/dev/null 2>&1; then
  nginx -t >/dev/null 2>&1 && nginx -s reload >/dev/null 2>&1 || true
fi

if [ "$PURGE" != 1 ] && [ "$KEEP" != 1 ]; then
  if [ -t 0 ]; then
    printf 'Delete models and config in %s and %s? [y/N] ' "$DATA" "$VOICESTUDIO_DEFAULT_ETC"
    read -r answer
    case "$answer" in
      y|Y|yes|YES) PURGE=1 ;;
      *) KEEP=1 ;;
    esac
  else
    log "No terminal attached. Keeping models and config. Re-run with --purge to delete them."
    KEEP=1
  fi
fi

if [ "$PURGE" = 1 ]; then
  log "Removing $DATA and $VOICESTUDIO_DEFAULT_ETC"
  rm -rf "$DATA" "$VOICESTUDIO_DEFAULT_ETC" /var/log/voicestudio
  if getent passwd "$VOICESTUDIO_SERVICE_USER" >/dev/null 2>&1; then
    userdel "$VOICESTUDIO_SERVICE_USER" 2>/dev/null || log "Left the ${VOICESTUDIO_SERVICE_USER} user in place (still logged in or busy)."
  fi
  if getent group "$VOICESTUDIO_SERVICE_USER" >/dev/null 2>&1; then
    groupdel "$VOICESTUDIO_SERVICE_USER" 2>/dev/null || true
  fi
  log "Models and config deleted."
else
  log "Kept models and config:"
  log "  $DATA"
  log "  $VOICESTUDIO_ENV_FILE"
  log "Re-run with --purge to remove them."
fi
