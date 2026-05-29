#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install -U pip

if [ -f "requirements-codespace.txt" ]; then
  python -m pip install -r requirements-codespace.txt
else
  python -m pip install -r requirements.txt
fi

python -m pip install -U pytest

echo "✅ Codespaces env listo. Venv: $(python -c 'import sys; print(sys.executable)')"

