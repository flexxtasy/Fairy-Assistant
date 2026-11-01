#!/usr/bin/env bash
# Launch FAIRY on the Wayland session from a headless context.
# Default brain: strata (local LLM at 127.0.0.1:8080).
# Default form: icon-only (Ramiro's standing preference).
#   FAIRY_FULL_BODY=1  -> allow the full-body emerge form
#   FAIRY_BRAIN=stub|discord|strata
#   FAIRY_STUB=1       -> same as FAIRY_BRAIN=stub
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/1000
export WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-1}
cd "$(dirname "$0")"
FORM="--icon-only"
[ -n "${FAIRY_FULL_BODY:-}" ] && FORM=""
BRAIN="${FAIRY_BRAIN:-strata}"
[ -n "${FAIRY_STUB:-}" ] && BRAIN=stub
exec nix-shell -p python3 python3Packages.pyside6 \
  ${FAIRY_DISCORD:+python3Packages.discord-py} \
  --run "python3 fairy.py --brain $BRAIN $FORM ${FAIRY_PIXEL:+--pixel}"
