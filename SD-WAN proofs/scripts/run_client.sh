#!/usr/bin/env bash
# Run sdwan_client.py from WSL and keep the console output as evidence.
# Credentials are read from ~/.sdwan_env (OUTSIDE the repo, chmod 600), e.g.:
#   export SDWAN_HOST=sandbox-sdwan-2.cisco.com
#   export SDWAN_USER=...            # from the DevNet sandbox page
#   export SDWAN_PASS=...
#   export SDWAN_PIN_SHA256=...      # optional, see sdwan_client.py docstring
# Usage: bash scripts/run_client.sh <label> <inventory|overlay|policy|all>
set -u
cd "$(dirname "$0")/.." || exit 1
label="$1"; shift
[ -f ~/.sdwan_env ] && source ~/.sdwan_env
out="evidence/logs/$(date -u +%Y%m%d-%H%M%S)_${label}.txt"
{
  echo "# command : sdwan_client.py $*"
  echo "# start   : $(date -u +%FT%TZ)"
  ~/.venvs/sdwan/bin/python scripts/sdwan_client.py "$@"
  echo "# exit    : $?"
  echo "# end     : $(date -u +%FT%TZ)"
} > "$out" 2>&1
cat "$out"
