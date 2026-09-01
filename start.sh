#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

echo "[Twitter Download] Checking runtime..."

if command -v uv >/dev/null 2>&1; then
    echo "[Runtime] uv"
    uv sync --locked
    if [ "${1:-}" = "--check" ]; then
        echo "[OK] uv environment and dependencies are ready."
        exit 0
    fi
    exec uv run --no-sync python gui.py
fi

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
else
    echo "[ERROR] Neither uv nor Python was found in PATH." >&2
    echo "Install uv from https://docs.astral.sh/uv/ or install Python 3.13+." >&2
    exit 1
fi

echo "[Runtime] $PYTHON_BIN"
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)'; then
    echo "[ERROR] Python 3.13 or newer is required." >&2
    exit 1
fi

if ! "$PYTHON_BIN" -c 'import httpx, PySide6, x_client_transaction' >/dev/null 2>&1; then
    echo "[Dependencies] Installing packages from requirements.txt..."
    "$PYTHON_BIN" -m pip install --disable-pip-version-check -r requirements.txt
fi

if [ "${1:-}" = "--check" ]; then
    echo "[OK] Python environment and dependencies are ready."
    exit 0
fi

if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ] && [ "$(uname -s)" != "Darwin" ]; then
    echo "[WARNING] No graphical display was detected; PySide6 may not be able to open a window." >&2
fi

exec "$PYTHON_BIN" gui.py
