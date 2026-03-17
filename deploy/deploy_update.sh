#!/usr/bin/env bash
set -euo pipefail

# One-command deploy for EcoNova Guardian updates.
# Run from anywhere on your Mac:
#   ./deploy/deploy_update.sh
# Optional overrides:
#   EC2_HOST=54.164.140.252 EC2_KEY=~/Downloads/econova-key.pem ./deploy/deploy_update.sh

EC2_HOST="${EC2_HOST:-54.164.140.252}"
EC2_USER="${EC2_USER:-ec2-user}"
EC2_KEY="${EC2_KEY:-$HOME/Downloads/econova-key.pem}"
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

sudo systemctl restart econova
sudo systemctl reload nginx

echo "--- Service status ---"
sudo systemctl is-active econova
sudo systemctl is-active nginx

echo "--- Health ---"
curl -s https://54-164-140-252.sslip.io/health || true
EOF

echo
echo "Deploy complete."
echo "Open: https://54-164-140-252.sslip.io"
