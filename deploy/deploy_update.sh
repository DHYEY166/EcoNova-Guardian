#!/usr/bin/env bash
set -euo pipefail

# One-command deploy for EcoNova Guardian updates.
# Run from anywhere on your Mac:
#   ./deploy/deploy_update.sh
# Optional overrides:
#   EC2_HOST=54.164.140.252 EC2_KEY=~/.ssh/econova-key.pem ./deploy/deploy_update.sh
#
# Prefer ~/.ssh after: ./deploy/setup_ssh_key.sh (avoids macOS blocking keys in Downloads)

EC2_HOST="${EC2_HOST:-54.164.140.252}"
EC2_USER="${EC2_USER:-ec2-user}"
if [[ -n "${EC2_KEY:-}" ]]; then
  :
elif [[ -f "$HOME/.ssh/econova-key.pem" ]]; then
  EC2_KEY="$HOME/.ssh/econova-key.pem"
else
  EC2_KEY="$HOME/Downloads/econova-key.pem"
fi
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/home/ec2-user/app}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ ! -f "$EC2_KEY" ]]; then
  echo "ERROR: SSH key not found at $EC2_KEY"
  exit 1
fi

echo "==> Deploy target: ${EC2_USER}@${EC2_HOST}"
echo "==> Using key: ${EC2_KEY}"

# Sync code (exclude local runtime/env artifacts)
rsync -az --delete \
  -e "ssh -i $EC2_KEY" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude ".env" \
  --exclude ".venv/" \
  --exclude "venv/" \
  --exclude "data/events.db" \
  "$REPO_ROOT/backend/" "${EC2_USER}@${EC2_HOST}:${REMOTE_APP_DIR}/backend/"

rsync -az --delete \
  -e "ssh -i $EC2_KEY" \
  "$REPO_ROOT/frontend/" "${EC2_USER}@${EC2_HOST}:${REMOTE_APP_DIR}/frontend/"

# Keep deploy config in sync too
rsync -az \
  -e "ssh -i $EC2_KEY" \
  "$REPO_ROOT/deploy/" "${EC2_USER}@${EC2_HOST}:${REMOTE_APP_DIR}/deploy/"

# Remote update/apply steps
ssh -i "$EC2_KEY" "${EC2_USER}@${EC2_HOST}" <<'EOF'
set -euo pipefail
cd /home/ec2-user/app

python3 -m pip install --user -r backend/requirements.txt

# Ensure nginx can read static files
chmod 755 /home/ec2-user /home/ec2-user/app /home/ec2-user/app/frontend
chmod 644 /home/ec2-user/app/frontend/index.html /home/ec2-user/app/frontend/app.js /home/ec2-user/app/frontend/styles.css

# Patch nginx API location if still on old regex (certbot may have edited this file — only touch the proxy regex)
NGX_CONF=/etc/nginx/conf.d/econova.conf
if [[ -f "$NGX_CONF" ]] && grep -Fq 'location ~ ^/(classify|feedback|stats|health)' "$NGX_CONF" \
  && ! grep -Fq 'health|visit)' "$NGX_CONF"; then
  sudo cp -a "$NGX_CONF" "${NGX_CONF}.bak.$(date +%s)"
  # Use # delimiter — | inside the pattern breaks sed when | is also the delimiter
  sudo sed -i 's#\^/(classify|feedback|stats|health)#^/(classify|feedback|stats|health|visit)#' "$NGX_CONF"
fi
sudo nginx -t

# Keep systemd unit in sync (ExecStart uses python3 -m uvicorn — matches pip install --user)
sudo cp /home/ec2-user/app/deploy/econova.service /etc/systemd/system/econova.service
sudo systemctl daemon-reload
sudo systemctl restart econova
sleep 2
sudo systemctl reload nginx

echo "--- Backend (direct, bypasses nginx) ---"
if ! curl -sf --max-time 5 http://127.0.0.1:8000/health; then
  echo ""
  echo "ERROR: FastAPI not responding on 127.0.0.1:8000 (nginx will return 502)."
  sudo systemctl status econova --no-pager -l || true
  sudo journalctl -u econova -n 60 --no-pager || true
  exit 1
fi
echo ""

echo "--- Service status ---"
sudo systemctl is-active econova
sudo systemctl is-active nginx

echo "--- Health (public HTTPS) ---"
curl -sS --max-time 10 https://54-164-140-252.sslip.io/health || true
EOF

echo
echo "Deploy complete."
echo "Open: https://54-164-140-252.sslip.io"
