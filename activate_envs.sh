#!/usr/bin/env bash

# Run setup from project root regardless of caller location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ACTIVATE="$SCRIPT_DIR/backend/venv/bin/activate"
ROOT_ACTIVATE="$SCRIPT_DIR/venv/bin/activate"
REQ_FILE="$SCRIPT_DIR/backend/requirements.txt"
STAMP_FILE="$SCRIPT_DIR/backend/.requirements.sha256"
FORCE_INSTALL=0
DEV_RELOAD=0

for arg in "$@"; do
  if [ "$arg" = "--force-install" ]; then
    FORCE_INSTALL=1
  elif [ "$arg" = "--dev-reload" ]; then
    DEV_RELOAD=1
  fi
done

if [ -f "$BACKEND_ACTIVATE" ]; then
  # Activate backend venv first; this is the primary environment.
  source "$BACKEND_ACTIVATE"
else
  echo "Missing: $BACKEND_ACTIVATE"
fi

if [ -f "$ROOT_ACTIVATE" ]; then
  source "$ROOT_ACTIVATE"
else
  echo "Skipped missing: $ROOT_ACTIVATE"
fi

CURRENT_HASH="$(shasum -a 256 "$REQ_FILE" | awk '{print $1}')"
SAVED_HASH=""
if [ -f "$STAMP_FILE" ]; then
  SAVED_HASH="$(cat "$STAMP_FILE")"
fi

if [ "$FORCE_INSTALL" -eq 1 ] || [ "$CURRENT_HASH" != "$SAVED_HASH" ]; then
  if [ "$FORCE_INSTALL" -eq 1 ]; then
    echo "Force install requested: installing backend dependencies..."
  else
    echo "requirements.txt changed (or first run): installing backend dependencies..."
  fi
  cd "$SCRIPT_DIR/backend" || exit 1
  pip install -r requirements.txt || exit 1
  printf '%s\n' "$CURRENT_HASH" > "$STAMP_FILE"
else
  echo "requirements.txt unchanged: skipping pip install"
fi

echo "Starting frontend server in a new Terminal window on http://localhost:8080 ..."
osascript << APPLESCRIPT
tell application "Terminal"
  do script "cd '$SCRIPT_DIR/frontend' && python3 -m http.server 8080"
end tell
APPLESCRIPT

# Fallback for cases where Terminal automation launches but server does not stay up.
sleep 1
if ! lsof -nP -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Frontend not listening on 8080 yet; starting fallback background server..."
  (cd "$SCRIPT_DIR/frontend" && nohup python3 -m http.server 8080 >/tmp/eco_frontend.log 2>&1 &)
fi

echo "Starting backend API  → http://localhost:8000"
echo "Frontend app         → http://localhost:8080"
cd "$SCRIPT_DIR/backend" || exit 1
if [ "$DEV_RELOAD" -eq 1 ]; then
  echo "Dev reload mode enabled"
  uvicorn main:app --reload \
    --reload-dir "$SCRIPT_DIR/backend" \
    --reload-exclude "venv/*" \
    --reload-exclude ".venv/*" \
    --reload-exclude "__pycache__/*" \
    --reload-exclude "*/site-packages/*" \
    --reload-exclude "*.sha256" \
    --host 0.0.0.0 --port 8000
else
  uvicorn main:app --host 0.0.0.0 --port 8000 --log-level warning
fi
