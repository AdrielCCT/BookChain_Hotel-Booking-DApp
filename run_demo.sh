#!/usr/bin/env bash
# Pipeline execution script: Compiles, deploys, and executes the complete booking scenario.
# Requirement: An active Ganache instance must be running in a separate terminal (./scripts/start_ganache.sh).

set -e
cd "$(dirname "$0")"

# Load Python virtual environment settings
source scripts/pick_python.sh

echo "[1/3] Compiling smart contracts..."
$PY scripts/compile.py

echo "[2/3] Deploying smart contracts to local EVM network..."
$PY scripts/deploy.py

echo "[3/3] Executing end-to-end booking scenario..."
$PY scripts/interact.py