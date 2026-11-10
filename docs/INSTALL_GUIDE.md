# VoiceStudio Install Guide

How to put VoiceStudio on a Linux VPS, sign in the first time, add a domain with HTTPS, update it, remove it, and fix common problems. The last section covers the desktop app.

Related manuals: [Admin Manual](ADMIN_MANUAL.md) · [User Manual](USER_MANUAL.md) · [DEPLOY.md](../DEPLOY.md) (technical reference)

---

## 1. What you need

| | Minimum | Recommended |
|---|---|---|
| OS | Ubuntu or Debian, **x86_64**, systemd as PID 1 | Ubuntu 22.04 / 24.04 LTS |
| RAM | **8 GB** (the 2.4 GB voice model has to fit in memory) | 16 GB for CPU-only use |
| Disk | **About 20 GB free** (Python environment of several GB, plus the 2.4 GB default model) | 40 GB if you add more engines |
| GPU | Not required | NVIDIA with a working driver (`nvidia-smi` lists the card) |
| Access | root or sudo, SSH | — |

Notes, taken from the scripts:

- Other distributions are refused (`/etc/debian_version` is checked).
- Without a GPU the installer uses CPU PyTorch wheels. It works, but the project describes CPU as about an order of magnitude slower.
- If `nvidia-smi -L` works, or `/proc/driver/nvidia/version` exists, CUDA wheels are installed instead. Those wheels need several extra GB of disk.
- No cloud API key is needed to install or to use the default OmniVoice model.

## 2. One-line install

```bash
curl -fsSL https://raw.githubusercontent.com/vibhvesh/voicestudio/main/scripts/install.sh | sudo bash
```

The repository is public, so no token is needed. The installer:

1. Installs `git curl ca-certificates ffmpeg libsndfile1 pkg-config build-essential xz-utils tar python3` when they are missing, then Node.js 22, Bun 1.4.2 and `uv`.
2. Clones the code into `/opt/voicestudio`.
3. Runs `bun install`, builds the Python environment (CPU or CUDA), and builds the web UI.
4. Creates the system user `voicestudio` and the folders `/var/lib/voicestudio` (data and models) and `/var/log/voicestudio`.
5. Writes `/etc/voicestudio/voicestudio.env` and generates an API key the first time.
6. Installs two systemd services: `voicestudio-api` on `127.0.0.1:3900` and `voicestudio-web` on `0.0.0.0:8787`.
7. Prints the URL and, **on first install only**, the API key.

The first install takes a while because of the Python and JavaScript downloads. Running the installer again is safe: it refreshes the code, rebuilds, and restarts. It does not change the API key and does not delete models.

### Options

Put options after `bash -s --`:

```bash
curl -fsSL https://raw.githubusercontent.com/vibhvesh/voicestudio/main/scripts/install.sh | sudo bash -s -- --port 9000
```

| Flag | Default | Meaning |
|---|---|---|
| `--prefix PATH` | `/opt/voicestudio` | Where the app code goes |
| `--data-dir PATH` | `/var/lib/voicestudio` | Models, database, cache |
| `--port PORT` | `8787` | Public web port. Must be above 1024 unless you use `--domain`. Ignored with `--domain` |
| `--api-port PORT` | `3900` | Loopback API port. Must differ from `--port` |
| `--bind ADDR` | `0.0.0.0` | Address the public port listens on |
| `--source PATH` | — | Copy a local checkout instead of cloning |
| `--repo URL` | `https://github.com/vibhvesh/voicestudio.git` | Git URL to clone |
| `--ref NAME` | `main` | Git branch |
| `--git-token TOK` | — | Token for a private mirror only |
| `--torch auto\|cpu\|cuda` | `auto` | Force CPU or CUDA wheels |
| `--domain NAME` | — | Public hostname. Turns on HTTPS through Caddy or nginx |
| `--tls caddy\|nginx` | `caddy` | Which HTTPS front end to use with `--domain` |
| `--email ADDR` | — | Let's Encrypt contact. Needed for nginx certificates |
| `--firewall` | off | Allow the needed ports in `ufw` and enable it |
| `--no-systemd` | off | Run as background processes, for containers without systemd |
| `--dry-run` | off | Print the plan and exit without changing anything |
| `-h`, `--help` | | Show help |

Environment variables the installer also reads: `VOICESTUDIO_REPO`, `VOICESTUDIO_REF`, `VOICESTUDIO_GIT_TOKEN`.

Preview first if you want:

```bash
curl -fsSL https://raw.githubusercontent.com/vibhvesh/voicestudio/main/scripts/install.sh | sudo bash -s -- --dry-run
```

## 3. Open the firewall

Only open the public port. **Never open 3900.**

Without a domain:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8787/tcp
sudo ufw enable
```

With a domain, open 80 and 443 instead of 8787. Your VPS provider may also have its own firewall or security group, and the same ports need to be open there.

`--firewall` runs these commands for you. It is off by default because enabling `ufw` can lock you out if SSH does not use the standard OpenSSH profile. Test a second SSH session before you close the first.

## 4. First login

1. **Save the API key.** The installer prints it at the end as `API key: ...`. If you lost it:
   ```bash
   sudo grep '^OMNIVOICE_API_KEY=' /etc/voicestudio/voicestudio.env
   ```
2. Open `http://<your-vps-ip>:8787` (or `https://your-domain`).
3. A **Remote backend** card asks for the **API key**. Paste it and click **Connect**. The browser trades the key for a session, so you won't be asked on every page.
4. The **setup wizard** appears the first time. It has four steps:
   1. **System check**: the server checks itself. Continue when it passes.
   2. **Model packs**: choose what to download. The default voice model `k2-fsa/OmniVoice` is about 2.4 GB. Nothing downloads until you click.
   3. **Privacy**: choose your analytics and privacy settings.
   4. **Enter studio**.
5. The admin panel is at `http://<your-vps-ip>:8787/#/admin`. See the [Admin Manual](ADMIN_MANUAL.md).

There are no usernames or passwords. The API key is the only credential. Anyone who has it gets full access, including the admin panel. Requests from the server itself (loopback) don't need the key.

### Sharing with a friend

Give them the URL and the API key. Nothing else is needed. To cut off access later, use **Admin → Access → Rotate key**.

## 5. Domain and HTTPS

1. Create a DNS **A record** for, say, `voices.example.com` pointing to the VPS IP. Wait until `dig +short voices.example.com` returns that IP.
2. Open ports 80 and 443.
3. Run the installer with the domain. Re-running is safe.

**Caddy (default, gets a certificate automatically):**

```bash
curl -fsSL https://raw.githubusercontent.com/vibhvesh/voicestudio/main/scripts/install.sh | sudo bash -s -- --domain voices.example.com
```

**nginx and certbot:**

```bash
curl -fsSL https://raw.githubusercontent.com/vibhvesh/voicestudio/main/scripts/install.sh | sudo bash -s -- --domain voices.example.com --tls nginx --email you@example.com
```

With nginx and no `--email`, the site is served over plain HTTP until you run it again with `--email`. If certbot fails (DNS not ready, or port 80 blocked), the HTTP site stays up and the installer prints why.

Caddy's config goes to `/etc/voicestudio/Caddyfile`. nginx's goes to `/etc/nginx/sites-available/voicestudio`. The installer replaces both files each time it runs, so don't hand-edit them.

## 6. Update

```bash
curl -fsSL https://raw.githubusercontent.com/vibhvesh/voicestudio/main/scripts/update.sh | sudo bash
# or, on the server
sudo bash /opt/voicestudio/scripts/update.sh
```

Update pulls the branch recorded at install time from GitHub, reinstalls dependencies, rebuilds the web UI, and restarts the services. It keeps the API key, the env file, the database, and the downloaded models. The piped form only works when VoiceStudio is already installed. The only option is `--no-systemd`.

If a GPU was added or removed since the last run, update notices and installs the matching PyTorch wheels.

You can also update from **Admin → Updates → Update now**.

## 7. Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/vibhvesh/voicestudio/main/scripts/uninstall.sh | sudo bash
```

| Command | Result |
|---|---|
| plain (piped) | Stops the services and deletes `/opt/voicestudio` and the proxy config. **Keeps** models and config, because a pipe has no terminal to ask you |
| `sudo bash /opt/voicestudio/scripts/uninstall.sh` | Same, but asks `Delete models and config ...? [y/N]` |
| `... \| sudo bash -s -- --keep-data` | Never deletes models or config |
| `... \| sudo bash -s -- --purge` | Also deletes `/var/lib/voicestudio`, `/etc/voicestudio`, `/var/log/voicestudio`, and the `voicestudio` user |

`--purge` and `--keep-data` can't be combined. The script refuses to delete a folder that isn't a VoiceStudio install. Packages it installed (Node, Bun, uv, ffmpeg, Caddy, nginx) are left in place.

## 8. Troubleshooting

### Everyday commands

```bash
systemctl status voicestudio-api voicestudio-web
sudo systemctl restart voicestudio-api voicestudio-web
journalctl -u voicestudio-api -u voicestudio-web -f          # live logs
journalctl -u voicestudio-api -n 200 --no-pager              # last 200 lines
curl -fsS http://127.0.0.1:3900/health                        # API health on the server
```

Without systemd (`--no-systemd`): `tail -f /var/log/voicestudio/api.log /var/log/voicestudio/web.log`. Panel updates log to `/var/log/voicestudio/update.log`.

### Common problems

| Symptom | Cause and fix |
|---|---|
| `These scripts target Ubuntu/Debian` | Use an Ubuntu or Debian VPS |
| `systemd is installed but not running` | Probably a container. Re-run with `--no-systemd` |
| `API did not become healthy on 127.0.0.1:3900` | Read `journalctl -u voicestudio-api`. Usually low RAM or disk, or a dependency failed to build |
| `Port NNN needs root` | Pick `--port` above 1024, or use `--domain` |
| `exists and is not a VoiceStudio git checkout` | The `--prefix` folder already holds something else. Remove it or pick another path |
| The page won't load from outside | The cloud provider's firewall or `ufw` is blocking 8787 (or 80/443) |
| The key prompt keeps coming back or says HTTP 401 | Wrong key, or it was rotated. Get the current one from the env file |
| HTTPS doesn't work | DNS isn't pointing at the VPS yet, or port 80 is closed. Check `journalctl -u voicestudio-web` (Caddy) or the certbot output (nginx) |
| Speech is very slow | Expected on CPU. Use a GPU VPS, or shorter text |
| Out of memory during the first generation | Use 8 GB or more of RAM, or add swap |
| `git fetch failed` on update | Network or GitHub problem. Models and config are not touched, so retry |
| Admin buttons say `service-control.sh is not installed` | Re-run the installer, or restart with `systemctl` by hand |

### Security self-check

From another computer:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://<ip>:8787/engines                                   # expect 401
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer <key>" http://<ip>:8787/engines  # expect 200
```

## 9. Desktop app (macOS / Linux)

This is a separate app for your own computer, not the VPS installer. The script is `scripts/desktop/install.sh`. It downloads the official Electron release from `github.com/debpalash/VoiceStudio/releases` and checks its SHA-256 checksum.

```bash
curl -fsSL https://raw.githubusercontent.com/vibhvesh/voicestudio/main/scripts/desktop/install.sh | sh
curl -fsSL https://raw.githubusercontent.com/vibhvesh/voicestudio/main/scripts/desktop/install.sh | sh -s -- --version X.Y.Z
curl -fsSL https://raw.githubusercontent.com/vibhvesh/voicestudio/main/scripts/desktop/install.sh | sh -s -- --uninstall
```

| Flag | Meaning |
|---|---|
| `--binary` | Install the published release (default) |
| `--version X.Y.Z` | Install a specific release |
| `--main` / `--source` | Build from upstream `main`. Needs git, Node 22+, Bun, and Rust/Cargo |
| `--uninstall` | Remove the app and keep settings, models, and projects |

It installs to `/Applications/VoiceStudio.app` (or `~/Applications`) on macOS and to `~/.local/bin/VoiceStudio` (an AppImage) on Linux. Set `VOICESTUDIO_INSTALL_DIR` to change the location. Quit VoiceStudio before running the script. Linux arm64 isn't supported. On Intel Macs the app opens, but the local backend needs Apple Silicon. Windows users install the `.exe` from GitHub Releases.
