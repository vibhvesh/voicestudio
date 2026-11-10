# Put the git tree in place, install JS and Python deps, build the web UI.

# Clone URL, with an optional token inserted as x-access-token. The token is
# never printed. A URL that already contains credentials is left alone.
repo_url_with_token() {
  local repo=$1 token=$2
  if [ -z "$token" ]; then
    printf '%s' "$repo"
    return
  fi
  case "$repo" in
    *://*:*@*) printf '%s' "$repo" ;;
    https://*)
      printf 'https://x-access-token:%s@%s' "$token" "${repo#https://}"
      ;;
    *) die "VOICESTUDIO_GIT_TOKEN only applies to an https:// repository URL" ;;
  esac
}

redact_url() {
  # Hide userinfo so a failed clone does not land the token in the log.
  printf '%s' "$1" | sed -E 's#(://)[^/@]+@#\1#'
}

sync_source_tree() {
  local source=$1 prefix=$2
  [ -d "$source" ] || die "Source directory does not exist: $source"
  [ -f "$source/backend/main.py" ] || die "Source is not a VoiceStudio checkout: $source"
  [ -f "$source/scripts/deploy/web_proxy.py" ] || die "Source is missing scripts/deploy/web_proxy.py (is this an old checkout?)"
  if [ "$source" = "$prefix" ]; then
    log "Using existing tree at $prefix"
    return
  fi
  log "Copying $source -> $prefix"
  mkdir -p "$prefix"
  # Keep a prefix-local .venv and node_modules across re-runs. The data
  # directory lives outside the tree, so it is not part of this copy.
  tar -C "$source" \
    --exclude .venv \
    --exclude node_modules \
    --exclude frontend/dist \
    -cf - . | tar -C "$prefix" -xf -
}

clone_or_update_repo() {
  local repo=$1 ref=$2 prefix=$3 token=$4
  local authed
  authed=$(repo_url_with_token "$repo" "$token")
  if [ -d "$prefix/.git" ]; then
    log "Updating git checkout in $prefix ($(redact_url "$repo") $ref)"
    git -C "$prefix" -c "safe.directory=$prefix" remote set-url origin "$authed"
    git -C "$prefix" -c "safe.directory=$prefix" fetch --tags origin "$ref"
    git -C "$prefix" -c "safe.directory=$prefix" checkout -B "$ref" "origin/$ref"
    git -C "$prefix" -c "safe.directory=$prefix" reset --hard "origin/$ref"
    # Drop the token from the stored remote so it is not sitting in .git/config.
    git -C "$prefix" -c "safe.directory=$prefix" remote set-url origin "$repo"
    return
  fi
  if [ -e "$prefix" ] && [ -n "$(ls -A "$prefix" 2>/dev/null || true)" ]; then
    die "$prefix exists and is not a VoiceStudio git checkout. Pass --source or remove it."
  fi
  log "Cloning $(redact_url "$repo") ($ref) into $prefix"
  mkdir -p "$(dirname "$prefix")"
  git clone --branch "$ref" "$authed" "$prefix"
  git -C "$prefix" remote set-url origin "$repo"
}

install_app_deps() {
  local prefix=$1 variant=$2
  log "JavaScript dependencies (bun install)"
  (cd "$prefix" && bun install)
  log "Python environment (OMNIVOICE_TORCH_VARIANT=$variant)"
  (cd "$prefix" && OMNIVOICE_TORCH_VARIANT="$variant" bun scripts/setup-api.mjs)
  log "Building the web UI"
  (cd "$prefix" && bun run build:web)
  [ -f "$prefix/frontend/dist/index.html" ] || die "frontend/dist/index.html is missing after the build"
  chmod 755 "$prefix/scripts/deploy/web_proxy.py"
}

chown_tree() {
  local prefix=$1 data=$2
  log "Giving $VOICESTUDIO_SERVICE_USER ownership of the app tree and data directory"
  chown -R "${VOICESTUDIO_SERVICE_USER}:${VOICESTUDIO_SERVICE_USER}" "$prefix" "$data" /var/log/voicestudio
  # The env file stays root-owned and group-readable.
  if [ -f "$VOICESTUDIO_ENV_FILE" ]; then
    chown "root:${VOICESTUDIO_SERVICE_USER}" "$VOICESTUDIO_ENV_FILE"
    chmod 0640 "$VOICESTUDIO_ENV_FILE"
  fi
}
