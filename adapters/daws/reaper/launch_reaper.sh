#!/bin/sh
# Launch REAPER with PYTHONHOME set for its embedded Python interpreter.
#
# Reaper loads the venv's libpython (uv-managed, arm64) to run reapy's in-Reaper
# server. That CPython is a python-build-standalone build whose baked-in prefix
# (/install) doesn't exist here, so when embedded it can't find its stdlib and
# Py_Initialize aborts -- crashing REAPER the moment reapy starts the server.
# Setting PYTHONHOME to the interpreter's real prefix fixes it (verified offline).
#
# This sets the var only for the REAPER process we exec -- NOT globally -- so other
# Python-embedding apps (e.g. Anki) are unaffected. Launch Reaper via this script
# (a Dock/Finder launch won't have PYTHONHOME). See memory: reapy-arm64-setup.
set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REAPER_BIN="/Applications/REAPER.app/Contents/MacOS/REAPER"

PYTHONHOME="$("$PROJECT_DIR/.venv/bin/python" -c 'import sys; print(sys.base_prefix)')"
export PYTHONHOME

echo "Launching REAPER with PYTHONHOME=$PYTHONHOME"
exec "$REAPER_BIN" "$@"
