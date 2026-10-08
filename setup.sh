#!/usr/bin/env bash
# Environment setup script: Python virtual environment, dependencies, and Ganache CLI

set -e
cd "$(dirname "$0")"

# Locate a valid Python interpreter on the system
for cand in python3 python py; do
  if $cand -c "import sys" >/dev/null 2>&1; then SYS_PY="$cand"; break; fi
done

echo "[1/3] Creating Python virtual environment (.venv)..."
$SYS_PY -m venv .venv
source scripts/pick_python.sh

echo "[2/3] Upgrading pip and installing required dependencies..."
$PY -m pip install --upgrade pip
$PY -m pip install -r requirements.txt

echo "[3/3] Installing Ganache CLI globally via npm..."
npm install -g ganache@7 || echo "Global installation failed. The runner script will fall back to npx."

echo "Setup completed successfully. Next step: run ./scripts/start_ganache.sh in a separate terminal."