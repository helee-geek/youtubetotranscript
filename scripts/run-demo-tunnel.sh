#!/usr/bin/env bash
# Free public demo: local app + Cloudflare Tunnel (uses your home IP — YouTube works).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${PORT:-8000}"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if ! python -c "import uvicorn" 2>/dev/null; then
  echo "Install dependencies first:"
  echo "  python -m venv .venv && source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "Install cloudflared (free, no account needed):"
  echo "  Ubuntu/Debian: sudo apt install cloudflared"
  echo "  macOS:         brew install cloudflared"
  echo "  Other:         https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
  exit 1
fi

echo "Starting app on http://127.0.0.1:${PORT} ..."
uvicorn main:app --host 127.0.0.1 --port "$PORT" &
APP_PID=$!

cleanup() {
  kill "$APP_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep 2

echo ""
echo "============================================================"
echo "  FREE PUBLIC DEMO — share the trycloudflare.com URL below"
echo "  Keep this terminal open during your presentation."
echo "============================================================"
echo ""

cloudflared tunnel --url "http://127.0.0.1:${PORT}"
