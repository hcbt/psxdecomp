#!/usr/bin/env bash
set -euo pipefail
root="${DEVENV_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$root"
python3 tools/gen_splat.py
shopt -s nullglob
yamls=(config/*.yaml)
if [ ${#yamls[@]} -eq 0 ]; then
  echo "no splat yamls in config/" >&2
  exit 1
fi
for y in "${yamls[@]}"; do
  splat split "$y"
done
