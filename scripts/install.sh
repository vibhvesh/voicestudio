#!/usr/bin/env bash
# VoiceStudio headless installer for Ubuntu/Debian (x86_64).
#
#   sudo bash scripts/install.sh
#   sudo bash scripts/install.sh --port 8787
#   sudo bash scripts/install.sh --domain voices.example.com --email you@example.com
#
# Piped (only works when this repository is publicly readable):
#   curl -fsSL https://cursor.com/codebase/vibhvesh-chandel/tmp-975794ea12dd953e/raw/main/scripts/install.sh | sudo bash
#
# A private repository returns a login page to curl, so the pipe never sees
# this script. Clone with git credentials, then run the file. See DEPLOY.md.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: sudo bash scripts/install.sh [options]

  --prefix PATH     App checkout (default /opt/voicestudio)
  --data-dir PATH   Models, database, cache (default /var/lib/voicestudio)
  --port PORT       Public web port (default 8787). Not used with --domain.
  --api-port PORT   Loopback API port (default 3900). Keep it off the firewall.
  --bind ADDR       Public listen address (default 0.0.0.0)
  --source PATH     Copy this checkout instead of git clone
  --repo URL        Git URL used when --source is omitted
  --ref NAME        Git branch (default main)
  --git-token TOK   https token for a private clone (or set VOICESTUDIO_GIT_TOKEN)
  --torch auto|cpu|cuda
                    auto (default) uses CUDA when nvidia-smi works, else CPU
  --domain NAME     Public hostname. Turns on the TLS reverse proxy.
  --tls caddy|nginx TLS frontend used with --domain (default caddy)
  --email ADDR      Let's Encrypt contact. Required for nginx certificates.
  --firewall        Allow the public port in ufw and enable ufw
  --no-systemd      Start background processes instead of systemd units
  --dry-run         Print the plan and exit
  -h, --help
EOF
}

# curl | bash has no file on disk. Clone the repo, then run the real script.
if [ ! -f "${BASH_SOURCE[0]:-}" ]; then
  if [ "$(id -u)" -ne 0 ]; then
    printf 'voicestudio: pipe this into sudo bash\n' >&2
    exit 1
  fi
  export DEBIAN_FRONTEND=noninteractive
  if ! dpkg -s git >/dev/null 2>&1 || ! dpkg -s ca-certificates >/dev/null 2>&1 || ! dpkg -s curl >/dev/null 2>&1; then
    apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update -qq
    apt-get install -y -qq git ca-certificates curl
  fi
  prefix=/opt/voicestudio
  repo="${VOICESTUDIO_REPO:-https://origin.cursor.com/git/vibhvesh-chandel/tmp-975794ea12dd953e.git}"
  ref="${VOICESTUDIO_REF:-main}"
  prev=
  for arg in "$@"; do
    case "$prev" in
      --prefix) prefix=$arg ;;
      --repo) repo=$arg ;;
      --ref) ref=$arg ;;
    esac
    prev=$arg
  done
  if [ -f "$prefix/scripts/install.sh" ]; then
    exec bash "$prefix/scripts/install.sh" "$@"
  fi
  if ! git clone --branch "$ref" "$repo" "$prefix"; then
    cat >&2 <<EOF
voicestudio: git clone failed for ${repo}.
This repository is private. curl cannot download the installer (the raw URL
redirects to a login page), and git clone needs a credential.

Simplest fix: make the repository public. Then the curl | sudo bash command
in DEPLOY.md works, and clone does not need a token.

Until then:
  git clone https://x-access-token:\$TOKEN@origin.cursor.com/git/vibhvesh-chandel/tmp-975794ea12dd953e.git
  cd <checkout>
  sudo bash scripts/install.sh
EOF
    exit 1
  fi
  exec bash "$prefix/scripts/install.sh" "$@"
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

PREFIX=$VOICESTUDIO_DEFAULT_PREFIX
DATA=$VOICESTUDIO_DEFAULT_DATA
WEB_PORT=$VOICESTUDIO_DEFAULT_WEB_PORT
API_PORT=$VOICESTUDIO_DEFAULT_API_PORT
WEB_HOST=0.0.0.0
SOURCE=
REPO=${VOICESTUDIO_REPO:-$VOICESTUDIO_DEFAULT_REPO}
REF=${VOICESTUDIO_REF:-$VOICESTUDIO_DEFAULT_REF}
GIT_TOKEN=${VOICESTUDIO_GIT_TOKEN:-}
TORCH=auto
DOMAIN=
TLS=caddy
EMAIL=
FIREWALL=0
NO_SYSTEMD=0
DRY_RUN=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX=$2; shift 2 ;;
    --data-dir) DATA=$2; shift 2 ;;
    --port) WEB_PORT=$2; shift 2 ;;
    --api-port) API_PORT=$2; shift 2 ;;
    --bind) WEB_HOST=$2; shift 2 ;;
    --source) SOURCE=$2; shift 2 ;;
    --repo) REPO=$2; shift 2 ;;
    --ref) REF=$2; shift 2 ;;
    --git-token) GIT_TOKEN=$2; shift 2 ;;
    --torch) TORCH=$2; shift 2 ;;
    --domain) DOMAIN=$2; shift 2 ;;
    --tls) TLS=$2; shift 2 ;;
    --email) EMAIL=$2; shift 2 ;;
    --firewall) FIREWALL=1; shift ;;
    --no-systemd) NO_SYSTEMD=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1 (see --help)" ;;
  esac
done

valid_port "$WEB_PORT" || die "Invalid --port"
valid_port "$API_PORT" || die "Invalid --api-port"
[ "$WEB_PORT" != "$API_PORT" ] || die "--port and --api-port must differ"
safe_abs_dir "$PREFIX"
safe_abs_dir "$DATA"
case "$TORCH" in
  auto|cpu|cuda) ;;
  *) die "--torch must be auto, cpu, or cuda" ;;
esac
case "$TLS" in
  caddy|nginx) ;;
  *) die "--tls must be caddy or nginx" ;;
esac
if [ -n "$DOMAIN" ] && [ "$TLS" = nginx ] && [ -z "$EMAIL" ]; then
  log "--email is unset. nginx will serve HTTP until you pass --email and re-run."
fi
if [ -z "$DOMAIN" ] && [ "$WEB_PORT" -lt 1024 ]; then
  die "Port ${WEB_PORT} needs root. Use a port above 1024, or --domain so Caddy/nginx binds 443."
fi

if [ "$TORCH" = auto ]; then
  TORCH=$(detect_torch_variant)
fi
WEB_MODE=proxy
PUBLIC_UI_PORT=$WEB_PORT
if [ -n "$DOMAIN" ]; then
  WEB_MODE=$TLS
  PUBLIC_UI_PORT=443
fi

if [ "$DRY_RUN" = 1 ]; then
  cat <<EOF
prefix:     $PREFIX
data:       $DATA
torch:      $TORCH
api:        127.0.0.1:$API_PORT
web:        ${DOMAIN:-$WEB_HOST:$WEB_PORT} (${WEB_MODE})
source:     ${SOURCE:-git $REPO $REF}
systemd:    $([ "$NO_SYSTEMD" = 1 ] && printf 'no' || printf 'yes')
EOF
  exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
  exec sudo -E bash "$SCRIPT_DIR/install.sh" "$@"
fi
require_root
prereq_all
ensure_service_user "$DATA"

if [ -n "$SOURCE" ]; then
  SOURCE=$(cd "$SOURCE" && pwd)
  sync_source_tree "$SOURCE" "$PREFIX"
else
  clone_or_update_repo "$REPO" "$REF" "$PREFIX" "$GIT_TOKEN"
fi

install_app_deps "$PREFIX" "$TORCH"
python3 "$PREFIX/scripts/deploy/web_proxy.py" --self-test

# Group must exist before the env file is locked down.
key_new=0
if [ -z "$(env_get OMNIVOICE_API_KEY)" ]; then
  key_new=1
  env_set OMNIVOICE_API_KEY "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
fi
env_set OMNIVOICE_BIND_HOST 127.0.0.1
env_set OMNIVOICE_PORT "$API_PORT"
env_set OMNIVOICE_UI_PORT "$PUBLIC_UI_PORT"
env_set OMNIVOICE_DATA_DIR "$DATA"
env_set HF_HOME "$DATA/huggingface"
env_set HF_HUB_CACHE "$DATA/huggingface/hub"
env_set OMNIVOICE_TORCH_VARIANT "$TORCH"
env_set OMNIVOICE_FRONTEND_DIST "$PREFIX/frontend/dist"
env_set VOICESTUDIO_PREFIX "$PREFIX"
env_set VOICESTUDIO_WEB_HOST "$WEB_HOST"
env_set VOICESTUDIO_WEB_PORT "$WEB_PORT"
env_set VOICESTUDIO_API_HOST 127.0.0.1
env_set VOICESTUDIO_API_PORT "$API_PORT"
env_set VOICESTUDIO_WEB_MODE "$WEB_MODE"
env_set VOICESTUDIO_DOMAIN "$DOMAIN"
env_set VOICESTUDIO_TLS "$TLS"
env_set VOICESTUDIO_REPO "$REPO"
env_set VOICESTUDIO_REF "$REF"
env_set HOME "$DATA"
env_set XDG_CACHE_HOME "$DATA/cache"
if [ -n "$DOMAIN" ]; then
  env_set OMNIVOICE_ALLOWED_HOSTS "$DOMAIN"
  env_set OMNIVOICE_ALLOWED_ORIGINS "https://${DOMAIN},http://127.0.0.1:${WEB_PORT},http://localhost:${WEB_PORT},app://voicestudio"
else
  # Same-origin UI. IP hosts are allowed without this list; keep loopback for local curls.
  env_set OMNIVOICE_ALLOWED_HOSTS ""
  env_set OMNIVOICE_ALLOWED_ORIGINS "http://127.0.0.1:${WEB_PORT},http://localhost:${WEB_PORT},app://voicestudio"
fi

if [ -n "$DOMAIN" ]; then
  write_tls_config "$DOMAIN" "$TLS" "$API_PORT" "$EMAIL"
fi

chown_tree "$PREFIX" "$DATA"
write_marker "$PREFIX"
install_units "$PREFIX" "$WEB_MODE"
start_services "$NO_SYSTEMD" "$API_PORT"
maybe_firewall "$FIREWALL" "$WEB_PORT" "$DOMAIN"
print_summary "$(public_url "$DOMAIN" "$WEB_PORT")" "$key_new" "$WEB_PORT" "$API_PORT" "$DOMAIN"
