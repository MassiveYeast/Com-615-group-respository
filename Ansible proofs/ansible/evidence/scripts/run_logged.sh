#!/usr/bin/env bash
# Run one Ansible command from the project dir and save its full output as evidence.
# Usage (from WSL):  bash evidence/scripts/run_logged.sh <label> <command...>
# Output: evidence/logs/<timestamp>_<label>.txt with command, start/end time, exit code, duration.
set -u
cd "$(dirname "$0")/../.." || exit 1
# shellcheck disable=SC1090
source ~/.venvs/ansible/bin/activate
label="$1"; shift
ts="$(date +%Y%m%d-%H%M%S)"
out="evidence/logs/${ts}_${label}.txt"
{
  echo "# command : $*"
  echo "# host    : control node $(hostname) ($(ansible --version | head -1))"
  echo "# start   : $(date --iso-8601=seconds)"
  echo
} > "$out"
start=$(date +%s%N)
ANSIBLE_FORCE_COLOR=0 "$@" >> "$out" 2>&1
rc=$?
end=$(date +%s%N)
ms=$(( (end - start) / 1000000 ))
{
  echo
  echo "# end     : $(date --iso-8601=seconds)"
  echo "# exit    : $rc"
  printf '# wall_s  : %d.%03d\n' $((ms / 1000)) $((ms % 1000))
} >> "$out"
echo "saved $out (exit $rc)"
exit $rc
