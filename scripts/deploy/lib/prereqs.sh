# Apt packages, Node 22, Bun, and uv. Each step is a no-op when already present.

prereq_apt() {
  local pkg missing=()
  for pkg in git curl ca-certificates ffmpeg libsndfile1 pkg-config build-essential xz-utils tar python3; do
    dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
  done
  if [ "${#missing[@]}" -eq 0 ]; then
    log "apt packages already installed (git, ffmpeg, libsndfile, compilers)"
    return
  fi
  log "Installing apt packages: ${missing[*]}"
  export DEBIAN_FRONTEND=noninteractive
  # A dead mirror must fail instead of hanging the installer.
  apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update -qq
  apt-get install -y -qq "${missing[@]}"
}

prereq_node() {
  if command -v node >/dev/null 2>&1; then
    local major
    major=$(node -p 'process.versions.node.split(".")[0]')
    if [ "$major" -ge 22 ]; then
      log "node $(node -v) already installed"
      return
    fi
    log "node $(node -v) is older than 22; installing Node.js 22 beside it"
  else
    log "Installing Node.js 22"
  fi
  local tarball=/tmp/node-v22.23.4-linux-x64.tar.xz
  curl -fsSL "https://nodejs.org/dist/v22.23.4/node-v22.23.4-linux-x64.tar.xz" -o "$tarball"
  tar -C /usr/local --strip-components=1 -xJf "$tarball"
  rm -f "$tarball"
  hash -r
  command -v node >/dev/null 2>&1 || die "node was not installed into /usr/local/bin"
  log "node $(node -v)"
}

prereq_bun() {
  if command -v bun >/dev/null 2>&1; then
    log "bun $(bun --version) already installed"
    return
  fi
  log "Installing bun 1.4.2"
  curl -fsSL https://bun.sh/install | env BUN_INSTALL=/usr/local bash -s "bun-v1.4.2"
  hash -r
  command -v bun >/dev/null 2>&1 || die "bun was not installed into /usr/local/bin"
  log "bun $(bun --version)"
}

prereq_uv() {
  if command -v uv >/dev/null 2>&1; then
    log "uv $(uv --version) already installed"
    return
  fi
  log "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
  hash -r
  command -v uv >/dev/null 2>&1 || die "uv was not installed into /usr/local/bin"
  log "uv $(uv --version)"
}

prereq_all() {
  require_debian
  prereq_apt
  prereq_node
  prereq_bun
  prereq_uv
}
