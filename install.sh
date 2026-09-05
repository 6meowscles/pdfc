#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python="${PYTHON:-python3}"

"$python" -m venv "$root/.venv"
"$root/.venv/bin/pip" install --upgrade pip
"$root/.venv/bin/pip" install -e "$root[dev]"

mkdir -p "$HOME/.local/bin"
ln -sf "$root/.venv/bin/pdfc" "$HOME/.local/bin/pdfc"

echo "installed: $HOME/.local/bin/pdfc"
"$HOME/.local/bin/pdfc" --version
