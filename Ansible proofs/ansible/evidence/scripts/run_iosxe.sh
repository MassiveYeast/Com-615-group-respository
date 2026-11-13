#!/usr/bin/env bash
# AN-07 runner: loads the user's DevNet reservation credentials and runs one logged phase.
# Usage (WSL, from "Ansible proofs/ansible"):
#   bash evidence/scripts/run_iosxe.sh precheck
#   bash evidence/scripts/run_iosxe.sh change   <interface>
#   bash evidence/scripts/run_iosxe.sh change   <interface>     # 2nd run = idempotency (T2)
#   bash evidence/scripts/run_iosxe.sh rollback <interface>
#
# ~/.iosxe_env (create it yourself, chmod 600, NEVER in the repo):
#   export IOSXE_HOST=...   IOSXE_PORT=22   IOSXE_USER=...   IOSXE_PASS=...
set -u
cd "$(dirname "$0")/../.." || exit 1
envf=~/.iosxe_env
[ -f "$envf" ] || { echo "NOT RUN: $envf missing (needs credentials from your DevNet reservation)"; exit 3; }
[ "$(stat -c %a "$envf")" = "600" ] || { echo "NOT RUN: $envf must be chmod 600"; exit 3; }
# shellcheck disable=SC1090
source "$envf"
case "${IOSXE_PASS:-}" in ""|PASTE_*) echo "NOT RUN: IOSXE_PASS not set in $envf"; exit 3;; esac
phase="${1:?phase}"; iface="${2:-}"
extra=(-e "phase=$phase")
[ -n "$iface" ] && extra+=(-e "iosxe_interface=$iface")
mkdir -p evidence/iosxe/raw
bash evidence/scripts/run_logged.sh "AN-07_${phase}" \
  ansible-playbook -i inventory/devnet_iosxe.yml playbooks/iosxe_interface_description.yml "${extra[@]}"
rc=$?

# Sanitised before/after diff of the whole running-config for change/rollback phases
if [ "$phase" != "precheck" ]; then
  b=$(ls -t evidence/iosxe/raw/*_"${phase}"_1before.cfg 2>/dev/null | head -1)
  a=$(ls -t evidence/iosxe/raw/*_"${phase}"_2after.cfg 2>/dev/null | head -1)
  if [ -n "$b" ] && [ -n "$a" ]; then
    clean() { grep -Ev 'secret|password|key-string|community|^Building configuration|^Current configuration|Last configuration change|NVRAM config last updated|^ *[0-9A-F]{8}( [0-9A-F]{8})+ *$' "$1"; }
    out="evidence/iosxe/$(basename "${a%_2after.cfg}")_config_diff.txt"
    { echo "# sanitised diff: $(basename "$b") -> $(basename "$a")"
      echo "# (lines with secrets/passwords/keys/certificates removed; shared sandbox - unrelated lines may be other users' changes)"
      diff -u <(clean "$b") <(clean "$a"); echo "# diff exit: $? (0 = identical, 1 = differences)"; } > "$out"
    echo "saved $out"
  fi
fi
exit $rc
