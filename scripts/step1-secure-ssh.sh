#!/bin/bash
# Perkins VPS - Step 1: Secure SSH
# Run this ON THE VPS after: ssh root@72.62.175.45

set -e
echo "=== Step 1: Secure SSH ==="

# Generate Ed25519 key
mkdir -p /root/.ssh
ssh-keygen -t ed25519 -C "perkins-vps" -N "" -f /root/.ssh/id_ed25519 2>/dev/null || true

echo ""
echo "--- ADD THIS PUBLIC KEY TO YOUR LOCAL MACHINE ---"
cat /root/.ssh/id_ed25519.pub
echo "--- END PUBLIC KEY ---"
echo ""
echo "Copy private key to your Mac (in another terminal): scp root@72.62.175.45:/root/.ssh/id_ed25519 ~/.ssh/perkins_vps && chmod 600 ~/.ssh/perkins_vps"
echo "Then: ssh -i ~/.ssh/perkins_vps root@72.62.175.45"
echo ""

# Allow this key for login (so Mac can use the private key after copying it)
grep -q "perkins-vps" /root/.ssh/authorized_keys 2>/dev/null || cat /root/.ssh/id_ed25519.pub >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys

# Backup and edit sshd_config
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.$(date +%Y%m%d)
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
# Ensure these are set
grep -q '^PasswordAuthentication' /etc/ssh/sshd_config || echo "PasswordAuthentication no" >> /etc/ssh/sshd_config
grep -q '^PubkeyAuthentication' /etc/ssh/sshd_config || echo "PubkeyAuthentication yes" >> /etc/ssh/sshd_config

echo "Restarting sshd..."
systemctl restart sshd

echo "Done. Test from your machine: ssh root@72.62.175.45 (should use key, no password)."
