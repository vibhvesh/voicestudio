# VoiceStudio Admin Manual

For the person who runs the VoiceStudio server. It covers every section of the admin panel, model downloads, the API key, updates, backups, logs, and security.

Related manuals: [Install Guide](INSTALL_GUIDE.md) · [User Manual](USER_MANUAL.md)

---

## 1. Opening the admin panel

Go to `http://<server>:8787/#/admin` (or `https://<your-domain>/#/admin`).

- A remote browser needs the **API key**. The first visit shows the **Remote backend** card. Paste the key and click **Connect**.
- A browser on the server itself (loopback) doesn't need the key.
- The installer sets `OMNIVOICE_SERVER_MODE=1`, which lets the key unlock the admin routes from outside.

The left sidebar ("Admin · Server control") has seven sections:

| Section | Hint shown | What it's for |
|---|---|---|
| Overview | Status at a glance | Version, update status, CPU, memory, services |
| Updates | Version and changelog | Compare with GitHub and click Update now |
| Settings | Environment and endpoints | Edit `/etc/voicestudio/voicestudio.env` |
| Models | Download and disk | Download or delete models, watch disk space |
| System | Resources, services, logs | Live gauges, Restart/Stop, log viewer |
| Access | API key | Rotate or revoke the key |
| Data | Storage and backup | Disk usage, audio cleanup, config export |

### Users and roles

VoiceStudio has **no user accounts, roles, or passwords**. One API key gives full access to the studio and the admin panel. Everyone you share the key with is effectively an admin. To remove someone, rotate the key (section 7) and give the new key only to the people who should keep access.

---

## 2. Overview

- Four tiles: **Version**, **Update** (*Available* or *Up to date*), **CPU** %, and **Memory** % (used / total).
- A **Services** card: the GPU name, or *"CPU inference. No NVIDIA GPU reported."*, plus the output of the service helper's `status` (for example `active` / `active`).
- Shortcut cards to the other six sections.

## 3. Updates

Three cards:

- **Installed**: the version and the 12-character git SHA on the server.
- **Latest on github.com/vibhvesh/voicestudio (main)**: *Update available*, *Current*, or *Unknown*, plus the latest SHA.
- **Action**: the **Update now** button. It changes to *Updating…* while running.

How **Update now** works: the panel calls the root-owned helper `/usr/local/lib/voicestudio/service-control.sh update`, which runs `scripts/update.sh`. That pulls the code, reinstalls dependencies, rebuilds the UI, and restarts. The API restarts at the end, so the page briefly loses its connection. Models, the env file, and the API key are kept.

Below the cards:
- **Changelog**: the first 80 lines of `CHANGELOG.md` on the server.
- **Update log**: the end of `/var/log/voicestudio/update.log`.
- A red *"Could not read origin: …"* line means the server couldn't reach GitHub.

Only one update runs at a time. The same thing from SSH: `sudo bash /opt/voicestudio/scripts/update.sh`.

## 4. Settings

The page shows the env file path, then **Restart services** and **Save** buttons, then settings grouped into cards.

- Secrets (marked *secret*) are never shown. The field says *"Configured — enter a new value to replace"*. Leave it empty to keep the current value.
- Settings marked **Restart required** only take effect after **Restart services**. Secrets and translation settings apply right away.
- *"File is not writable by the service."* means the env file permissions are wrong. Run the installer again to fix them (it sets `root:voicestudio`, mode `0660`).
- Ports must be 1–65535, paths must be absolute, URLs must start with http(s), and every value must be a single line.

| Group | Label | Env key | Options / format | Restart |
|---|---|---|---|---|
| Network | API port | `OMNIVOICE_PORT` | port | yes |
| Network | Web bind address | `VOICESTUDIO_WEB_HOST` | text (`0.0.0.0` = all interfaces) | yes |
| Network | Web port | `VOICESTUDIO_WEB_PORT` | port | yes |
| Compute | PyTorch build | `OMNIVOICE_TORCH_VARIANT` | `cpu`, `cuda`, `rocm`, `auto` | yes, and a dependency reinstall |
| Compute | Inference device | `OMNIVOICE_DEVICE` | Automatic, `cpu`, `cuda`, `mps` | yes |
| Storage | Data directory | `OMNIVOICE_DATA_DIR` | absolute path | yes |
| Storage | Hugging Face home | `HF_HOME` | absolute path | yes |
| Storage | Hugging Face hub cache | `HF_HUB_CACHE` | absolute path | yes |
| Storage | Web UI build | `OMNIVOICE_FRONTEND_DIST` | absolute path | yes |
| Secrets | Hugging Face token | `HF_TOKEN` | secret, optional. Needed for gated models such as **pyannote** | no |
| Translation | OpenAI API key | `OPENAI_API_KEY` | secret, optional | no |
| Translation | Translation base URL | `TRANSLATE_BASE_URL` | OpenAI-compatible URL. For Ollama: `http://127.0.0.1:11434/v1` | no |
| Translation | Translation API key | `TRANSLATE_API_KEY` | secret, optional | no |
| Translation | Translation model | `TRANSLATE_MODEL` | model name, for example `llama3.1` for Ollama | no |
| Speech | Whisper / ASR backend | `OMNIVOICE_ASR_BACKEND` | engine id, for example `faster-whisper` or `whisperx`. Empty uses the default | yes |

Care points:
- After changing the **Web port**, open the new port in the firewall. If you use a domain, re-run the installer with `--domain` instead.
- After changing the **PyTorch build**, run `sudo bash /opt/voicestudio/scripts/update.sh` so the matching wheels get installed. Note that update.sh detects the GPU itself and writes `cpu` or `cuda` back.
- If you move the **Data directory** or model caches, copy the old contents there first and make sure the `voicestudio` user owns the new folder.

## 5. Models

- Tiles: **Installed** (n / total), **On disk**, and **Disk free**, plus a disk usage bar.
- Running downloads appear as lines like `state: repo · NN%`. The page refreshes every 2 s while a download runs.
- **Filter models** searches by name, repo id, or role.
- The table lists **Model**, **Role**, and **Size** (estimated GB, or the actual size once installed), with **Download** or **Delete** per row.

Nothing downloads until you click **Download**. Downloads go to the Hugging Face cache (`/var/lib/voicestudio/huggingface/hub` by default).

| Model | Notes |
|---|---|
| `k2-fsa/OmniVoice` | The default speech model, about 2.4 GB. Needed for TTS, cloning, and dubbing voices |
| Whisper family (WhisperX, Faster-Whisper, …) | Speech-to-text for transcription and dubbing |
| pyannote (speaker diarization) | Gated on Hugging Face. Accept the model terms on huggingface.co, then set **Settings → Hugging Face token** |
| Translation | Not a download here. Point **Settings → Translation** at OpenAI, Ollama, or any OpenAI-compatible server |

Check that **Disk free** is larger than the model size before downloading. Deleting a model frees its cache folder right away.

## 6. System

- **Restart** and **Stop** buttons, handled by the service helper. **Stop takes the whole site down**, and the panel can't start it again. Use SSH: `sudo systemctl start voicestudio-api voicestudio-web`.
- Gauges for **CPU** (with core count), **Memory**, and **Disk** (free space), refreshed every 5 s.
- A **Compute** card: GPU name or *CPU only*, PyTorch variant, device, and version.
- Service status output.
- Log tabs: **api**, **web**, **update**, and **omnivoice.log**. Each shows the last 20 000 characters. *"That log is not available yet."* means the file doesn't exist.

The api and web files under `/var/log/voicestudio/` are only written in `--no-systemd` mode. Under systemd, use `journalctl -u voicestudio-api -u voicestudio-web`. `omnivoice.log` lives in the data directory.

## 7. Access (API key)

- Shows *Configured (abcd…wxyz)* and the env file path.
- **Rotate key** (or **Generate key** if none is set) makes a new random key. The old one stops working immediately.
- **Revoke key** also issues a replacement. It never clears the key, because an empty key would leave the public port open.
- The new key appears once in a yellow box: *"Copy this key now. It will not be shown again."*

After rotating, everyone else gets the key prompt again and needs the new key. If you lose it, read it from the server:

```bash
sudo grep '^OMNIVOICE_API_KEY=' /etc/voicestudio/voicestudio.env
```

## 8. Data

- Tiles: **App data**, **Generated audio**, **Database** (`omnivoice.db`), and **Models**, each with its size and path.
- **Delete audio older than (days)**, default 30, then **Clean generated audio**. `0` deletes **all** generated audio. It only touches the generated-audio folder. Projects, voices, the database, and models are left alone. Deleted files can't be recovered.
- **Export config** downloads the env file with secrets blanked out. **Export config with secrets** includes the API key and tokens, so keep that file private.

### Backups

The panel doesn't back up audio or projects for you. Do it over SSH:

```bash
sudo systemctl stop voicestudio-web voicestudio-api
sudo tar -czf voicestudio-backup-$(date +%F).tgz \
  /etc/voicestudio \
  --exclude=/var/lib/voicestudio/huggingface \
  /var/lib/voicestudio
sudo systemctl start voicestudio-api voicestudio-web
```

Models are left out because you can download them again. Leave out the `--exclude` line to include them. To restore, install VoiceStudio, stop the services, extract the archive to `/`, run `sudo chown -R voicestudio:voicestudio /var/lib/voicestudio`, and start the services.

---

## 9. Command-line reference

```bash
systemctl status voicestudio-api voicestudio-web
sudo systemctl restart voicestudio-api voicestudio-web
journalctl -u voicestudio-api -u voicestudio-web -f
sudo bash /opt/voicestudio/scripts/update.sh
sudo bash /opt/voicestudio/scripts/install.sh --domain voices.example.com   # add HTTPS later
sudo bash /opt/voicestudio/scripts/uninstall.sh [--keep-data | --purge]
python3 /opt/voicestudio/scripts/deploy/web_proxy.py --self-test
```

| Path | Contents |
|---|---|
| `/opt/voicestudio` | App code (replaced on update) |
| `/etc/voicestudio/voicestudio.env` | All settings and the API key (`root:voicestudio`, 0660) |
| `/etc/voicestudio/Caddyfile` | Caddy config, when using `--domain` |
| `/var/lib/voicestudio` | Database, projects, generated audio, model cache |
| `/var/log/voicestudio` | update.log, and api/web logs in no-systemd mode |
| `/usr/local/lib/voicestudio/service-control.sh` | Root helper for status, restart, stop, and update |
| `/etc/sudoers.d/voicestudio` | Lets the service user run only that helper's four commands |

## 10. Security notes

- **Never expose port 3900.** The API listens on loopback only, and the proxy is its only client.
- The proxy, Caddy, and nginx all **replace** `X-Forwarded-For`, so a client can't pretend to be loopback. Check with `web_proxy.py --self-test` and the curl test in the Install Guide (expect 401 without the key and 200 with it).
- Use **HTTPS** (`--domain`) whenever the server is on the internet. Over plain HTTP the key travels unencrypted.
- The key is your only lock. Rotate it whenever someone should lose access, or if it leaks.
- The service runs as the unprivileged `voicestudio` user. Its sudo rights are limited to four commands of one helper script.
- Keep `Export config with secrets` files and backups private. They contain the key.
- Allow SSH in `ufw` before enabling it.
- Licensing: the app is AGPL-3.0, and model weights and generated or cloned voices have their own terms (see `LICENSE-NOTICE.md`). Only clone voices you have permission to use.
