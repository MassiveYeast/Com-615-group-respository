#!/usr/bin/env bash
# AN-10: repeated drift -> detect -> correct -> idempotency cycles (T2, T3, S1).
# Usage (WSL, from "Ansible proofs/ansible"):  bash evidence/scripts/drift_cycles.sh [cycles] [limit]
#
# Each cycle introduces the same five drifts by hand (as a careless admin would), then:
#   2_detect   playbook --check --diff   expect changed > 0, nothing altered
#   3_correct  playbook                  expect changed > 0
#   4_rerun    playbook                  expect changed = 0  (idempotency)
#   5_verify   read-only state check     expect baseline values back
# None of the drifts can cut SSH: port 22 stays allowed and the sshd file is only edited
# (sshd is reloaded only by the playbook, after "sshd -t" validates the restored file).
set -u
cd "$(dirname "$0")/../.." || exit 1
# shellcheck disable=SC1090
source ~/.venvs/ansible/bin/activate
cycles="${1:-3}"
limit="${2:-linux_servers}"
L=evidence/scripts/run_logged.sh
summary="evidence/logs/$(date +%Y%m%d-%H%M%S)_AN-10_drift_cycles_summary.csv"
echo "cycle,step,log,exit,wall_s,ok,changed,unreachable,failed" > "$summary"

DRIFT='set -e
echo "server 192.0.2.123 iburst  # AN-10 drift" >> /etc/chrony/chrony.conf
sed -i "s/^MaxAuthTries .*/MaxAuthTries 6/" /etc/ssh/sshd_config.d/10-nel-hardening.conf
echo "<p>AN-10 unauthorised edit</p>" >> /var/www/nel/index.html
systemctl disable chrony 2>&1
ufw allow 8080/tcp comment "AN-10 unapproved rule"
echo drift-introduced'

VERIFY='sha256sum /etc/chrony/chrony.conf /etc/ssh/sshd_config.d/10-nel-hardening.conf /var/www/nel/index.html
sshd -T | grep -i "^maxauthtries"
echo "chrony enabled: $(systemctl is-enabled chrony)"
ufw show added
curl -s -o /dev/null -w "http %{http_code}\n" http://localhost/'

recap() {  # sum ok/changed/unreachable/failed over every host in a log's PLAY RECAP
  awk '/PLAY RECAP/{f=1;next} f&&/ok=/{for(i=1;i<=NF;i++){split($i,a,"=");if(a[1]~/^(ok|changed|unreachable|failed)$/)s[a[1]]+=a[2]}}
       END{printf "%d,%d,%d,%d",s["ok"],s["changed"],s["unreachable"],s["failed"]}' "$1"
}
run() {  # run <cycle> <step> <command...>
  local c=$1 s=$2 out f rc w
  shift 2
  out=$(bash "$L" "AN-10_c${c}_${s}" "$@"); rc=$?
  f=$(echo "$out" | sed -n 's/^saved \(.*\) (exit.*/\1/p')
  w=$(sed -n 's/^# wall_s  : //p' "$f")
  echo "$c,$s,$(basename "$f"),$rc,$w,$(recap "$f")" >> "$summary"
  echo "cycle $c $s: exit $rc, ${w}s"
}

for c in $(seq 1 "$cycles"); do
  run "$c" 1_introduce ansible "$limit" -m ansible.builtin.shell -a "$DRIFT"
  run "$c" 2_detect    ansible-playbook playbooks/linux_servers.yml --limit "$limit" --check --diff
  run "$c" 3_correct   ansible-playbook playbooks/linux_servers.yml --limit "$limit"
  run "$c" 4_rerun     ansible-playbook playbooks/linux_servers.yml --limit "$limit"
  run "$c" 5_verify    ansible "$limit" -m ansible.builtin.shell -a "$VERIFY"
done

# Pass/fail per cycle, written next to the CSV (the CSV itself is the raw result)
awk -F, 'NR>1{k=$1; if($2=="2_detect")d[k]=$7; if($2=="3_correct")c[k]=$7; if($2=="4_rerun")r[k]=$7; if($4!=0)e[k]=1}
  END{for(k in d){ok=(d[k]>0 && c[k]>0 && r[k]==0 && !e[k]); printf "cycle %s: detect changed=%s, correct changed=%s, rerun changed=%s -> %s\n",k,d[k],c[k],r[k],(ok?"PASS":"FAIL")}}' \
  "$summary" | sort | tee "${summary%.csv}_verdict.txt"
echo "summary: $summary"
