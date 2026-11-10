# Deploy VoiceStudio on a Linux VPS

Headless install for Ubuntu/Debian x86_64. The API listens on loopback. A small
proxy (or Caddy/nginx when you pass a domain) publishes the web UI. Remote
browsers are not loopback, so the installer generates `OMNIVOICE_API_KEY` and
stores it in `/etc/voicestudio/voicestudio.env` (mode `0640`, group
`voicestudio`). The UI asks for that key once and exchanges it for a session.

CPU wheels are the default. If `nvidia-smi` can see a GPU, setup installs the
CUDA wheels instead. Override with `--torch cpu` or `--torch cuda`.

The scripts are split so a failure is local:

| File | Role |
|---|---|
| `scripts/install.sh` | Entry point |
| `scripts/update.sh` | Pull, rebuild, restart. Keeps the env file and models |
| `scripts/uninstall.sh` | Stop services and delete the app tree |
| `scripts/deploy/lib/` | Apt, git, env file, systemd, TLS |
| `scripts/deploy/web_proxy.py` | Public port → `127.0.0.1:3900`, with forwarding headers rewritten |

The Electron desktop installer is `scripts/desktop/install.sh`. It is not this VPS installer.

## One-liners

Raw base (this repository, branch `main`):

```text
https://cursor.com/codebase/vibhvesh-chandel/tmp-975794ea12dd953e/raw/main/
```

| Script | URL |
|---|---|
| Install | `https://cursor.com/codebase/vibhvesh-chandel/tmp-975794ea12dd953e/raw/main/scripts/install.sh` |
| Update | `https://cursor.com/codebase/vibhvesh-chandel/tmp-975794ea12dd953e/raw/main/scripts/update.sh` |
| Uninstall | `https://cursor.com/codebase/vibhvesh-chandel/tmp-975794ea12dd953e/raw/main/scripts/uninstall.sh` |

**These URLs require authentication.** The repository is private. An unauthenticated `curl` does not receive the script: `https://cursor.com/codebase/.../raw/main/scripts/install.sh` answers **307** to a Cursor login page, and a git access token sent as `Authorization: Bearer` is not accepted there either. `git clone` of `https://origin.cursor.com/git/vibhvesh-chandel/tmp-975794ea12dd953e.git` also asks for a username when no credential is configured.

`curl | bash` therefore cannot install this copy until the repository is public.

**Simplest fix:** make the repository public. After that, the same raw URLs should return the shell files, `git clone` of the origin URL needs no token, and the commands below work as written.

Until then, clone with a git credential and run the file (this is what actually works):

```bash
git clone https://x-access-token:$TOKEN@origin.cursor.com/git/vibhvesh-chandel/tmp-975794ea12dd953e.git
cd tmp-975794ea12dd953e
sudo bash scripts/install.sh
```

Do not commit the token. On later updates, root's git must be able to fetch. Either make the repo public, or export `VOICESTUDIO_GIT_TOKEN` for `sudo -E bash scripts/update.sh`.

Once the raw URLs serve the files without a login, the one-liners are:

```bash
curl -fsSL https://cursor.com/codebase/vibhvesh-chandel/tmp-975794ea12dd953e/raw/main/scripts/install.sh | sudo bash

curl -fsSL https://cursor.com/codebase/vibhvesh-chandel/tmp-975794ea12dd953e/raw/main/scripts/update.sh | sudo bash

curl -fsSL https://cursor.com/codebase/vibhvesh-chandel/tmp-975794ea12dd953e/raw/main/scripts/uninstall.sh | sudo bash
```

Pass flags after `--`:

```bash
curl -fsSL https://cursor.com/codebase/vibhvesh-chandel/tmp-975794ea12dd953e/raw/main/scripts/install.sh | sudo bash -s -- --port 8787
curl -fsSL https://cursor.com/codebase/vibhvesh-chandel/tmp-975794ea12dd953e/raw/main/scripts/install.sh | sudo bash -s -- --domain voices.example.com --email you@example.com
curl -fsSL https://cursor.com/codebase/vibhvesh-chandel/tmp-975794ea12dd953e/raw/main/scripts/uninstall.sh | sudo bash -s -- --purge
```

## What the installer does

1. Installs `git`, `curl`, `ffmpeg`, `libsndfile`, compilers, Node.js 22 (if missing), Bun 1.4.2, and `uv`.
2. Clones or updates the repo into `/opt/voicestudio` (or copies `--source`).
3. Runs `bun install`, `bun scripts/setup-api.mjs` (CPU or CUDA), and `bun run build:web`.
4. Creates the system user `voicestudio` and `/var/lib/voicestudio` for the database and Hugging Face cache.
5. Writes `/etc/voicestudio/voicestudio.env`. An existing API key is kept.
6. Installs `voicestudio-api.service` (Uvicorn on `127.0.0.1:3900`) and `voicestudio-web.service` (public proxy on `0.0.0.0:8787`).
7. Prints the URL and, the first time only, the API key.

Re-running `install.sh` is safe. It refreshes the tree, rebuilds, and restarts. It does not rotate the API key or delete models.

With `--domain`, the web service is Caddy (`--tls caddy`, the default) or nginx (`--tls nginx`). Caddy requests a certificate by itself. nginx uses certbot when `--email` is set. DNS must already point at the VPS, and ports 80 and 443 must be reachable. The loopback API port stays closed.

## Manual build

```bash
sudo apt-get update
sudo apt-get install -y git curl ca-certificates ffmpeg libsndfile1 pkg-config build-essential python3

# Node 22, Bun 1.4.2, and uv if you don't already have them.
curl -fsSL https://nodejs.org/dist/v22.23.4/node-v22.23.4-linux-x64.tar.xz | sudo tar -C /usr/local --strip-components=1 -xJ
curl -fsSL https://bun.sh/install | sudo env BUN_INSTALL=/usr/local bash -s "bun-v1.4.2"
curl -LsSf https://astral.sh/uv/install.sh | sudo env UV_INSTALL_DIR=/usr/local/bin sh

sudo git clone https://origin.cursor.com/git/vibhvesh-chandel/tmp-975794ea12dd953e.git /opt/voicestudio
cd /opt/voicestudio

# cuda when nvidia-smi works; otherwise cpu
export OMNIVOICE_TORCH_VARIANT=cpu
bun install
bun scripts/setup-api.mjs
bun run build:web

sudo useradd --system --home-dir /var/lib/voicestudio --shell /usr/sbin/nologin voicestudio
sudo install -d -o voicestudio -g voicestudio -m 0750 /var/lib/voicestudio/huggingface

python3 -c 'import secrets; print(secrets.token_urlsafe(32))'   # put this in the env file
```

`/etc/voicestudio/voicestudio.env` (group `voicestudio`, mode `0640`):

```bash
OMNIVOICE_API_KEY=replace-me
OMNIVOICE_BIND_HOST=127.0.0.1
OMNIVOICE_PORT=3900
OMNIVOICE_UI_PORT=8787
OMNIVOICE_DATA_DIR=/var/lib/voicestudio
HF_HOME=/var/lib/voicestudio/huggingface
HF_HUB_CACHE=/var/lib/voicestudio/huggingface/hub
OMNIVOICE_TORCH_VARIANT=cpu
OMNIVOICE_FRONTEND_DIST=/opt/voicestudio/frontend/dist
VOICESTUDIO_PREFIX=/opt/voicestudio
VOICESTUDIO_WEB_HOST=0.0.0.0
VOICESTUDIO_WEB_PORT=8787
VOICESTUDIO_API_HOST=127.0.0.1
VOICESTUDIO_API_PORT=3900
VOICESTUDIO_WEB_MODE=proxy
HOME=/var/lib/voicestudio
XDG_CACHE_HOME=/var/lib/voicestudio/cache
```

API unit, `/etc/systemd/system/voicestudio-api.service`:

```ini
[Service]
User=voicestudio
WorkingDirectory=/opt/voicestudio
EnvironmentFile=/etc/voicestudio/voicestudio.env
ExecStart=/usr/local/bin/uv run --no-sync uvicorn main:app --app-dir backend --host 127.0.0.1 --port ${OMNIVOICE_PORT} --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=on-failure
```

Web unit, same directory, `voicestudio-web.service`:

```ini
[Service]
User=voicestudio
EnvironmentFile=/etc/voicestudio/voicestudio.env
ExecStart=/usr/bin/python3 /opt/voicestudio/scripts/deploy/web_proxy.py
Restart=on-failure
```

Then:

```bash
sudo chown -R voicestudio:voicestudio /opt/voicestudio /var/lib/voicestudio
sudo systemctl daemon-reload
sudo systemctl enable --now voicestudio-api.service voicestudio-web.service
curl -fsS http://127.0.0.1:3900/health
```

Open `http://<vps>:8787`. Paste the API key when the page asks. The first session is a setup wizard. Generating speech downloads `k2-fsa/OmniVoice` (about 2.4 GB) after you confirm.

Check a proxy header bug with a non-loopback address. `/engines` must be **401** without the key and **200** with `Authorization: Bearer <key>`. A client that sends `X-Forwarded-For: 127.0.0.1` must still be 401. The proxy strips that header.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://<public-ip>:8787/engines
curl -sS -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $OMNIVOICE_API_KEY" http://<public-ip>:8787/engines
```

From the VPS itself, `curl http://127.0.0.1:8787/engines` is loopback and is allowed without the key. That is the API's rule, not a bypass of remote clients.

## Sizing

| | CPU-only | NVIDIA |
|---|---|---|
| When | `nvidia-smi` fails or you pass `--torch cpu` | Driver installed and `nvidia-smi` lists a GPU |
| Disk | About 20 GB free. The Python env is several GB and the default voice model is 2.4 GB. Use 40 GB if you will add more engines. | Same data, plus the larger CUDA wheels (several extra GB). |
| RAM | 8 GB is the practical minimum so the process and the 2.4 GB model can reside in memory. 16 GB is more comfortable for CPU inference. | System RAM still matters. Weights also occupy GPU memory; a small card will fall back or run out during synthesis. |
| Speed | Usable, much slower than a GPU. The project describes CPU as roughly an order of magnitude slower. | Selected automatically. Force it with `--torch cuda`. |

The web UI and `/health` do not load the voice model. The first synthesis does.

No cloud key is required for the local UI or for the public OmniVoice weights. Optional later:

- Hugging Face token for faster downloads and for gated diarization models (pyannote).
- `OPENAI_API_KEY` or another OpenAI-compatible server for LLM translation.
- Do not publish port 3900. The key is for clients of the public origin.

## Firewall

| Port | Open? | Why |
|---|---|---|
| 22 | Yes | SSH. Allow this before enabling ufw. |
| 8787 (or `--port`) | Yes, if you are not using a domain | Web UI and the API on the same origin |
| 80 and 443 | Yes, with `--domain` | Caddy or nginx |
| 3900 | No | Loopback API. The proxy on this machine is the only client. |

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8787/tcp
sudo ufw enable
```

`install.sh --firewall` runs those commands. It can lock you out if SSH is not on the OpenSSH profile, so the default is to print them and not enable ufw.

## Update and uninstall

```bash
sudo bash /opt/voicestudio/scripts/update.sh
sudo bash /opt/voicestudio/scripts/uninstall.sh              # asks before deleting models
sudo bash /opt/voicestudio/scripts/uninstall.sh --keep-data  # never delete models or the env file
sudo bash /opt/voicestudio/scripts/uninstall.sh --purge      # delete models, env, and the service user
```

Update runs `git fetch` as root. On a private repository that fails until root has a credential. The data directory is not inside the git tree, so a reset of `/opt/voicestudio` does not delete models.

## Logs

```bash
journalctl -u voicestudio-api -u voicestudio-web -f
# without systemd (--no-systemd, or a container where systemd is not PID 1):
tail -f /var/log/voicestudio/api.log /var/log/voicestudio/web.log
```

`python3 scripts/deploy/web_proxy.py --self-test` checks that a forged `X-Forwarded-For: 127.0.0.1` is discarded.
