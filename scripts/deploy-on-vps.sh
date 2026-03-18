#!/bin/bash
# Run on VPS (as root) to finish Step 1 and run Steps 2–7.
# Option A: git clone https://github.com/Vortilon/perkins.git /root/perkins && cd /root/perkins && bash scripts/deploy-on-vps.sh
# Option B: run from repo root after clone/pull

set -e
PERKINS_ROOT="${PERKINS_ROOT:-/root/perkins}"
if [ ! -f "$PERKINS_ROOT/main.py" ]; then
  git clone https://github.com/Vortilon/perkins.git "$PERKINS_ROOT" || true
fi
cd "$PERKINS_ROOT" || { echo "Clone repo first: git clone https://github.com/Vortilon/perkins.git $PERKINS_ROOT"; exit 1; }

echo "=== Step 1 (finish): SSH hardening ==="
mkdir -p /root/.ssh
PUBKEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOGPls0CVn4Jw0I6q5/9BiAEmqVUtsqicAZw54M4WzXu perkins-vps"
grep -q "perkins-vps" /root/.ssh/authorized_keys 2>/dev/null || echo "$PUBKEY" >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
if grep -q "^PasswordAuthentication yes" /etc/ssh/sshd_config 2>/dev/null; then
  sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
  sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
  systemctl restart sshd
  echo "Password auth disabled; sshd restarted."
fi

echo "=== Step 2: System update & base tools ==="
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git curl build-essential libgl1 libglib2.0-0 nginx

echo "=== Step 3: Ollama + model ==="
if ! command -v ollama &>/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
systemctl enable ollama 2>/dev/null || true
systemctl start ollama 2>/dev/null || true
sleep 3
ollama list | grep -q "qwen2.5:3b-instruct" || ollama pull qwen2.5:3b-instruct
ollama list | grep -q "perkins-ai" || ollama create perkins-ai -f "$PERKINS_ROOT/Modelfile"

echo "=== Step 4: Project (already in $PERKINS_ROOT) ==="
git remote -v | grep -q origin || git remote add origin https://github.com/Vortilon/perkins.git
git fetch origin 2>/dev/null || true

echo "=== Step 5/6: Code in place ==="

echo "=== Step 7: venv + systemd ==="
python3 -m venv "$PERKINS_ROOT/venv"
"$PERKINS_ROOT/venv/bin/pip" install -r "$PERKINS_ROOT/requirements.txt" -q
install -m 644 "$PERKINS_ROOT/scripts/perkins.service" /etc/systemd/system/perkins.service
systemctl daemon-reload
systemctl enable --now perkins
echo "Perkins service enabled and started."

echo "=== Optional: Nginx proxy (port 80) ==="
if [ -d /etc/nginx/sites-available ]; then
  cp "$PERKINS_ROOT/scripts/nginx-perkins.conf" /etc/nginx/sites-available/perkins
  ln -sf /etc/nginx/sites-available/perkins /etc/nginx/sites-enabled/perkins 2>/dev/null || true
  nginx -t 2>/dev/null && systemctl reload nginx && echo "Nginx reloaded; Perkins on port 80." || echo "Nginx not reloaded (check config)."
fi

echo "=== Done. Test: curl -s http://127.0.0.1:8000/ping ==="
curl -s http://127.0.0.1:8000/ping || true
