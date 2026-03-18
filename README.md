# Perkins AI

Private 24/7 AI backend on Ubuntu VPS for aviation-technical reasoning: compare customer report text (PDF/Excel/Word) vs MPD via **Qwen2.5-3B-Instruct** (Ollama, CPU-only).

- **FastAPI** on port 8000: `POST /analyze`, `GET /chat`, `GET /ping`
- **Ollama** model `perkins-ai` (Modelfile with MSG-3/ATA system prompt)
- **systemd** service + optional nginx proxy on 80

## Deploy on VPS (one-liner)

SSH in, then run (clone + full setup):

```bash
git clone https://github.com/vortilon/perkins.git /root/perkins && cd /root/perkins && bash scripts/deploy-on-vps.sh
```

Or if repo already at `/root/perkins`:

```bash
cd /root/perkins && git pull && bash scripts/deploy-on-vps.sh
```

## Test

```bash
curl -s http://72.62.175.45:8000/ping
curl -X POST http://72.62.175.45:8000/analyze -H "Content-Type: application/json" -d '{"report_text": "Landing gear uplock replaced at 12,500 FC.", "mpd_context": "32-210-00 Uplock actuator, 15,000 FC, ATA 32."}'
```

Open `http://72.62.175.45:8000/chat` for the web UI.

## Logs

```bash
journalctl -u perkins -f
```

## SSH (after Step 1)

Copy private key to Mac once, then use key-only login:

```bash
scp root@72.62.175.45:/root/.ssh/id_ed25519 ~/.ssh/perkins_vps && chmod 600 ~/.ssh/perkins_vps
ssh -i ~/.ssh/perkins_vps root@72.62.175.45
```
