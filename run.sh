#!/usr/bin/env bash
# BRM Territory Hub -- start the app (Mac/Linux)
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Setting up (first run only)..."
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

echo "Starting BRM Territory Hub..."
echo "Open http://127.0.0.1:5000 in your browser. Press Ctrl+C to stop."
./.venv/bin/python app.py
