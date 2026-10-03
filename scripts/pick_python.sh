#!/usr/bin/env bash
# Finds a python command that actually works.
# (On Windows, python3 can just be the MS Store shortcut, so we gotta test it.)
PY=""
for cand in ".venv/Scripts/python.exe" ".venv/bin/python" python3 python py; do
  if $cand -c "import sys" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python not found. Install Python 3.10+ from python.org" >&2
  exit 1
fi