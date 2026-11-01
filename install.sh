#!/usr/bin/env bash
# One-shot installer for generic Linux (Ubuntu, Fedora, Arch, Mint, ...).
# Creates a private venv and installs Fairy's only dependency (PySide6).
set -euo pipefail
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "python3 is required first"; exit 1; }
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install "PySide6>=6.6"

cat <<'DONE'

Fairy installed. Examples:
  # point her at a local model server (see docs/engines-and-models.md):
  ./.venv/bin/python fairy.py --brain strata --strata-url http://127.0.0.1:8080 --icon-only
  # no model yet? canned-reply mode to see the UI immediately:
  ./.venv/bin/python fairy.py --brain stub --icon-only

DONE
