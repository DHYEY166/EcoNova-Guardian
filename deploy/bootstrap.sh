#!/bin/bash
# EcoNova Guardian – EC2 bootstrap script
# Run this ONCE after SSH-ing into a fresh Amazon Linux 2023 t3.micro.
# The EC2 MUST have the EcoNovaBedrockRole IAM Instance Role attached.
# No AWS keys are needed anywhere in this script.

set -euo pipefail

REPO="https://github.com/DHYEY166/EcoNova-Guardian.git"
APP_DIR="/home/ec2-user/app"

echo "=== 1. System packages ==="
sudo dnf update -y
sudo dnf install -y git python3.11 python3.11-pip nginx

echo "=== 2. Python CLI alias ==="
sudo alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.11 1

echo "=== 3. Clone repo ==="
cd /home/ec2-user
git clone "$REPO" app

echo "=== 4. Python dependencies ==="
cd "$APP_DIR"
pip3 install --user -r backend/requirements.txt

echo "=== 5. Data directory ==="
mkdir -p "$APP_DIR/data"

echo "=== 6. Systemd service ==="
sudo cp "$APP_DIR/deploy/econova.service" /etc/systemd/system/econova.service
sudo systemctl daemon-reload
sudo systemctl enable --now econova

echo "=== 7. nginx ==="
# --- Replace YOUR_DOMAIN with your sslip.io address ---
# Get current public IP and build sslip.io domain
PUB_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
SSLIP_DOMAIN="$(echo "$PUB_IP" | tr '.' '-').sslip.io"
echo "Your domain will be: $SSLIP_DOMAIN"

# Install nginx config and set domain
sudo cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/conf.d/econova.conf
sudo sed -i "s/YOUR_DOMAIN/$SSLIP_DOMAIN/g" /etc/nginx/conf.d/econova.conf

sudo systemctl enable --now nginx

echo "=== 8. HTTPS with Let's Encrypt (certbot) ==="
sudo dnf install -y python3-certbot-nginx
sudo certbot --nginx -d "$SSLIP_DOMAIN" --non-interactive --agree-tos -m admin@example.com --redirect

echo ""
echo "========================================"
echo " Deployment complete!"
echo " App URL: https://$SSLIP_DOMAIN"
echo "========================================"
echo ""
echo " Check backend: sudo systemctl status econova"
echo " Backend logs:  sudo journalctl -u econova -f"
echo " nginx logs:    sudo tail -f /var/log/nginx/error.log"
