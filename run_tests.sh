#!/usr/bin/env bash
# Test runner script: Executes the automated test suite against an active Ganache node.

set -e
cd "$(dirname "$0")"

# Load Python virtual environment settings
source scripts/pick_python.sh

# Run Pytest in verbose mode
echo "Running automated smart contract tests..."
$PY -m pytest tests -v