# AN-07 to AN-10 - controlled improvement plan (written 13 Nov 2026, before execution)

Status legend: **NOT RUN** = waiting for approval or input · **DONE** = executed, log saved · **FAILED** = executed, did not succeed.
Results are added to `docs/EXPERIMENTS.md` (EXP-13 onwards) only after each step has really run.

## 0. Audit (read-only, 13 Nov 2026 01:05-01:17 UTC)

| Item | Found | Evidence |
|---|---|---|
| VMs | srv-main-01 (192.168.56.21) and srv-acq-01 (.22) running; Ansible SSH works | log 33 |
| Firewall | Both: default deny in / allow out, only 22/tcp and 80/tcp allowed. The AN-04 8080 rule no longer exists (srv-acq-01 was rebuilt for AN-06), so the "unmanaged rule" limitation must be re-created on purpose to test it | log 33 |
| Host keys | **Still identical on both VMs** (ED25519 `SHA256:VjufUgJC…Enlc`, ECDSA, RSA all `root@vagrant`) - EXP-11 finding still open | logs 33, 35 |
| Control node `known_hosts` | One hashed ED25519 entry per VM | audit output |
| Router `rtr-main-01` | Never imported (D-07) - AN-07 still blocked on the lab side | EXP-01 |
| DevNet IOS XE sandbox | `devnetsandboxiosxe.cisco.com` resolves; tcp/22, 443, 830 open. **Not logged in**: static credentials were rejected in EXP-01, a reservation is needed | probe 13 Nov 01:05 |
| Control node network modules | cisco.ios 11.6.0, ansible.netcommon 8.7.1, paramiko present, **ansible-pylibssh not installed** → the sandbox inventory uses `paramiko` (no install) | audit output |

New code (lint: yamllint OK, ansible-lint production profile passed):

| File | Purpose |
|---|---|
| `roles/linux_baseline/tasks/firewall.yml` + defaults + `group_vars/linux_servers.yml` | Approved policy (deny in, allow out, 22/tcp + 80/tcp only) with **pruning** of any other rule; SSH lock-out guard |
| `playbooks/rotate_host_keys.yml` | Detect shared host keys (read-only by default); rotate only with `-e hostkey_rotate=true`, one server at a time, with backup + rescue |
| `evidence/scripts/drift_cycles.sh` | N cycles of drift → `--check --diff` → correct → rerun, CSV summary + PASS/FAIL per cycle |
| `inventory/devnet_iosxe.yml`, `playbooks/iosxe_interface_description.yml`, `evidence/scripts/run_iosxe.sh` | AN-07 on the DevNet sandbox: precheck / change / rollback with on-device verification; credentials only from `~/.iosxe_env` |

Dry runs already done (no change on any host):
- log 34: `linux_servers.yml --check --diff` with the new firewall code → **changed=0 on both hosts** (today's rules are all approved, nothing would be deleted).
- log 35: `rotate_host_keys.yml` detect-only → **both hosts flagged "SHARED"**, rotation skipped.

## Safety net for every step (approve once)

```powershell
# Windows, in "Ansible proofs\ansible\lab"
vagrant snapshot save srv-main-01 pre-AN08-10
vagrant snapshot save srv-acq-01  pre-AN08-10
```
Recovery paths, in order:
1. **Console**: VirtualBox Manager → `nel-srv-acq-01` → Show → log in as `vagrant` (bento default password `vagrant` - *not tested in this lab*) → `sudo ufw allow 22/tcp` or `sudo ufw disable`.
2. **Snapshot**: `vagrant snapshot restore srv-acq-01 pre-AN08-10` (rolls back the whole VM).
3. **Rebuild**: `vagrant destroy -f srv-acq-01; vagrant up srv-acq-01`, then `ansible-playbook playbooks/linux_servers.yml` (proven in AN-06, log 27).

Note: `vagrant ssh` also uses port 22 (via NAT), so it is **not** a recovery path for a firewall lock-out - but it **is** one for a host-key problem (Vagrant ignores known_hosts).

## 1. AN-08 - fully managed firewall (S1, T3) - DONE 13 Nov 01:29-01:36 UTC (EXP-13, PASS)

Canary first: srv-acq-01, then srv-main-01. WSL, in `Ansible proofs/ansible`, `L=evidence/scripts/run_logged.sh`:

```bash
# 1 seed two unapproved rules + a temporary listener on 8080 (so blocking can be proven)
bash $L 36_AN-08_seed_unapproved ansible srv-acq-01 -m ansible.builtin.shell -a \
 "ufw allow 8080/tcp comment 'AN-08 unapproved test'; ufw allow from 192.168.56.0/24 to any port 3306 proto tcp; systemd-run --unit=an08-listener python3 -m http.server 8080; sleep 1; ufw show added"
# 2 prove 8080 is reachable before
bash $L 37_AN-08_probe_before curl -s -m 5 -o /dev/null -w "8080 -> http %{http_code}\n" http://192.168.56.22:8080/
# 3 detect (changes nothing)
bash $L 38_AN-08_check_diff ansible-playbook playbooks/linux_servers.yml --limit srv-acq-01 --check --diff
# 4 enforce on the canary
bash $L 39_AN-08_apply_srv-acq-01 ansible-playbook playbooks/linux_servers.yml --limit srv-acq-01
# 5 verify: fresh SSH session, ufw state, 8080 blocked, 80 still served
bash $L 40_AN-08_verify bash -c 'ssh -o ControlMaster=no -i ~/.ssh/nel_ansible_ed25519 ansible@192.168.56.22 "sudo ufw status verbose; sudo ufw show added"; curl -s -m 5 -o /dev/null -w "8080 -> http %{http_code}\n" http://192.168.56.22:8080/; curl -s -m 5 -o /dev/null -w "80 -> http %{http_code}\n" http://192.168.56.22/'
# 6 whole estate + idempotency
bash $L 41_AN-08_apply_all ansible-playbook playbooks/linux_servers.yml
bash $L 42_AN-08_rerun_idempotency ansible-playbook playbooks/linux_servers.yml
# 7 clean up the test listener
bash $L 43_AN-08_cleanup ansible srv-acq-01 -m ansible.builtin.command -a "systemctl stop an08-listener"
```
Expected: 3 reports the two rules as "would be removed" (changed>0); 4 deletes exactly those two; 5 shows `8080 -> http 000` (timeout) and `80 -> http 200`; 6 changed=0 on srv-main-01, 7 changed=0 everywhere.
**Stop rule:** any `UNREACHABLE` → stop, recovery path 1 or 2.
Disconnect risk: low - the SSH rule is in the approved list, is applied first, and the play refuses to run without it - but deleting firewall rules on a live host is exactly the kind of change you asked to approve.

## 2. AN-09 - unique SSH host keys (S1, T4) - DONE 13 Nov 01:36-01:38 UTC (EXP-14, PASS)

```bash
bash $L 44_AN-09_rotate ansible-playbook playbooks/rotate_host_keys.yml -e hostkey_rotate=true
bash $L 45_AN-09_verify bash -c 'for h in 192.168.56.21 192.168.56.22; do echo "== $h"; ssh -o StrictHostKeyChecking=yes -o ControlMaster=no -i ~/.ssh/nel_ansible_ed25519 ansible@$h "hostname; for f in /etc/ssh/ssh_host_*_key.pub; do ssh-keygen -lf \$f; done"; done'
bash $L 46_AN-09_old_key_rejected bash -c 'ssh -o UserKnownHostsFile=$HOME/.ssh/known_hosts.pre-rotation-srv-acq-01 -o StrictHostKeyChecking=yes -o ControlMaster=no -o BatchMode=yes -i ~/.ssh/nel_ansible_ed25519 ansible@192.168.56.22 true'   # expected to FAIL: "REMOTE HOST IDENTIFICATION HAS CHANGED"
bash $L 47_AN-09_rerun_detect ansible-playbook playbooks/rotate_host_keys.yml -e hostkey_rotate=true                                 # expected: both "unique", changed=0
```
Plus from Windows: `vagrant ssh srv-acq-01 -c hostname` (proves the out-of-band path still works).
What happens: per server, back up keys to `/root/ssh-hostkey-backup/` and `known_hosts` to `~/.ssh/known_hosts.pre-rotation-<host>`; delete keys; `ssh-keygen -A`; `sshd -t`; **reload** ssh (current session stays); read new key over the open authenticated session; replace the known_hosts entry; drop the connection; reconnect with host-key checking. On any failure the rescue restores the old keys and the run stops before the second server.
Rollback (only if needed; it re-creates the vulnerability): on the VM via `vagrant ssh` → `sudo cp -a /root/ssh-hostkey-backup/ssh_host_* /etc/ssh/ && sudo systemctl reload ssh`; on the control node → `cp ~/.ssh/known_hosts.pre-rotation-srv-acq-01 ~/.ssh/known_hosts`.
Afterwards (separate approval): delete `/root/ssh-hostkey-backup/` once verified.

## 3. AN-10 - repeated drift / idempotency (T2, T3, S1) - DONE 13 Nov 01:38-01:48 UTC (EXP-15, 3/3 PASS)

```bash
bash evidence/scripts/drift_cycles.sh 3
```
Each cycle on both servers: chrony.conf extra server, sshd `MaxAuthTries 6` (file only), web page edit, chrony disabled at boot, unapproved `ufw allow 8080/tcp` → `--check --diff` → correct → rerun → read-only verify. Output: 15 logs + `*_AN-10_drift_cycles_summary.csv` + `*_verdict.txt` (PASS = detect changed>0, correct changed>0, rerun changed=0, no non-zero exit). SSH stays allowed throughout; sshd is only reloaded after `sshd -t` validates the restored file.

## 4. AN-07 - IOS XE on the DevNet sandbox (T1, T2, T3) - NOT RUN: sandbox session launched 13 Nov 01:44 UTC (ends 07:44), waiting for the user to add the device password

Needs **you** to reserve/open the IOS XE sandbox at developer.cisco.com and copy the host/port/username/password it shows, then in WSL:
```bash
cat > ~/.iosxe_env <<'EOF'
export IOSXE_HOST='<from reservation>' IOSXE_PORT='<from reservation>' IOSXE_USER='<...>' IOSXE_PASS='<...>'
EOF
chmod 600 ~/.iosxe_env
```
Then:
```bash
bash evidence/scripts/run_iosxe.sh precheck                 # read-only: version, privilege 15?, interfaces, config backup
bash evidence/scripts/run_iosxe.sh change   <interface>     # records original, sets test description, verifies on device
bash evidence/scripts/run_iosxe.sh change   <interface>     # 2nd run: expect changed=0 (T2)
bash evidence/scripts/run_iosxe.sh rollback <interface>     # restores original / removes ours, verifies on device
```
Interface choice is made **after** the precheck: a Loopback interface (never GigabitEthernet1, the management interface the session runs over). A description does not affect forwarding. Full configs stay in the gitignored `evidence/iosxe/raw/`; sanitised diffs go to `evidence/iosxe/`.
Recovery: the only change is one `description` line; manual rollback = `configure terminal` → `interface <x>` → `no description` (or the recorded original from `evidence/iosxe/*_original.json`). A shared sandbox can be reset by Cisco or changed by other users at any time - the precheck/after backups record what was really there.
If no reservation is possible, AN-07 stays **NOT RUN** and is reported as such.
