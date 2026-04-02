#!/usr/bin/env bash
# Run this on YOUR Mac in Terminal.app (not a sandboxed IDE terminal) if:
#   ssh says: Load key "...": Operation not permitted
#
# Usage:
#   ./deploy/setup_ssh_key.sh
# Optional:
#   SOURCE_KEY=~/path/to/key.pem ./deploy/setup_ssh_key.sh

set -euo pipefail

SOURCE_KEY="${SOURCE_KEY:-$HOME/Downloads/econova-key.pem}"
DEST_KEY="${DEST_KEY:-$HOME/.ssh/econova-key.pem}"

if [[ ! -f "$SOURCE_KEY" ]]; then
  echo "ERROR: Key not found: $SOURCE_KEY"
  exit 1
fi

echo "==> Source: $SOURCE_KEY"
if xattr -l "$SOURCE_KEY" 2>/dev/null | grep -q com.apple.quarantine; then
  echo "==> Removing com.apple.quarantine from source..."
  xattr -d com.apple.quarantine "$SOURCE_KEY"
else
  echo "==> No quarantine on source (OK)."
fi

mkdir -p "$HOME/.ssh"
cp "$SOURCE_KEY" "$DEST_KEY"
chmod 600 "$DEST_KEY"
echo "==> Installed: $DEST_KEY (mode 600)"
echo
echo "Test SSH:"
echo "  ssh -i $DEST_KEY ec2-user@54.164.140.252"
echo "(Use your instance IP if different.)"
echo
echo "Deploy:"
echo "  ./deploy/deploy_update.sh"
