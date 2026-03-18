# Perkins AI

Private 24/7 AI backend on Ubuntu VPS for aviation-technical reasoning: compare customer report text (PDF/Excel/Word) vs MPD via **Qwen2.5-3B-Instruct** (Ollama, CPU-only).

- **Web:** https://perkins.noteify.us — login page (ChatGPT/Grok style), then chat UI
- **FastAPI** on port 8000: `POST /analyze`, `GET /chat`, `GET /ping` (auth required except `/ping`)
- **Ollama** model `perkins-ai` (Modelfile with MSG-3/ATA system prompt)
- **systemd** service + nginx proxy on 80 (server_name: perkins.noteify.us)

## Deploy on VPS (one-liner)

SSH in, then run (clone + full setup):

```bash
git clone https://github.com/Vortilon/perkins.git /root/perkins && cd /root/perkins && bash scripts/deploy-on-vps.sh
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

Open **https://perkins.noteify.us** (or http://72.62.175.45) for login, then chat. Set `PERKINS_PASSWORD` and `PERKINS_SECRET` in `/root/perkins/.env` on the VPS (see `.env.example`).

## Logs

```bash
journalctl -u perkins -f
```

## SSH (after Step 1)

Copy private key to Mac once (use password when prompted), then use key-only login:

```bash
scp root@72.62.175.45:/root/.ssh/id_ed25519 ~/.ssh/perkins_vps && chmod 600 ~/.ssh/perkins_vps
ssh -i ~/.ssh/perkins_vps root@72.62.175.45
```

**Optional – short host name:** Add to `~/.ssh/config` on your Mac:

```
Host perkins
  HostName 72.62.175.45
  User root
  IdentityFile ~/.ssh/perkins_vps
```

Then connect with: `ssh perkins`

---

## Login and env (perkins.noteify.us)

On the VPS, create `/root/perkins/.env` (copy from `.env.example`) and set:

- **PERKINS_PASSWORD** — password for the web login page
- **PERKINS_SECRET** — random string (e.g. 32+ chars) for signing session cookies

Then: `systemctl daemon-reload && systemctl restart perkins`

---

## Fine-tuning and next steps

### Fine-tuning the model (Perkins AI behavior)

1. **Edit the system prompt** in `Modelfile` (aviation/MSG-3 instructions, few-shot examples). Then on the VPS:
   ```bash
   cd /root/perkins && ollama create perkins-ai -f Modelfile
   systemctl restart perkins
   ```
2. **Ollama parameters**: In `Modelfile`, adjust `PARAMETER temperature` (e.g. 0.2 for focused, 0.4 for more variation) and `PARAMETER num_ctx` (context length).
3. **Larger model**: For better reasoning you can switch to a bigger Qwen (e.g. 7B) in the Modelfile; ensure the VPS has enough RAM.

### Suggested next steps

| Step | What | Why |
|------|------|-----|
| **HTTPS** | Add TLS (e.g. Certbot for perkins.noteify.us) | Secure login and API. |
| **MPD source** | Connect `mpd_context` to a real DB or API | Replace manual paste with live MPD data. |
| **Structured output** | Ask the model for JSON or add a small parser | More reliable discrepancies/recommendations. |
| **File upload** | Accept PDF/Excel/Word, extract text, then analyze | End-to-end “upload report → analysis”. |
| **Logo** | Replace “DAE” placeholder in `templates/login.html` with your image | Add `<img src="/static/logo.png" alt="DAE">` and serve from `/static`. |
| **Audit log** | Log analyses (and optionally store) | Traceability and debugging. |
