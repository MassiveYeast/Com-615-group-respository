# Experiment log

Every entry is from a command that was actually run. Raw outputs are in `evidence/logs/` (file names start with the run timestamp).

## Environment (2026-10-29)

| Item | Value |
|------|-------|
| Host | Windows 11 Pro 10.0.26300, 16 logical CPUs, 31.4 GB RAM |
| Control node | WSL 3.0.3, Ubuntu 24.04.5 LTS, Python 3.12.3 |
| Ansible | ansible-core 2.21.5, ansible-lint 26.10.1, yamllint 1.38.0 |
| Collections | cisco.ios 11.6.0, ansible.netcommon 8.7.1, ansible.posix 2.2.2, community.general 13.5.0 |
| Hypervisor | VirtualBox 7.2.16, Vagrant 2.4.9, box `bento/ubuntu-24.04` v202510.26.0 |

---

## EXP-01 - Cisco DevNet always-on IOS XE sandbox as network target

- **Goal:** use a public IOS XE device while the CSR1000v image is unavailable.
- **Method:** TCP tests from Windows to `devnetsandboxiosxe.cisco.com` and `devnetsandboxiosxec8k.cisco.com` on ports 22/443/830; SSH login from WSL with the previously published credentials (`admin` and `developer`, with the formerly published shared password [redacted 2026-11-12 – retired public sandbox credential; removed so the repo holds no plaintext credentials, S3]).
- **Result:** all ports open; SSH reached the password prompt (server banner `Cisco-1.25`) but **every login was rejected: "Permission denied"**.
- **Cause:** Cisco now generates credentials per reservation (shown in the sandbox "Quick Access" tab after logging in with a Cisco account). The old static credentials are no longer valid.
- **Outcome:** stopped trying (no repeated guessing against a third-party system). Network target stays the CSR1000v (D-07). The DevNet sandbox remains an option if a reservation is made.

## EXP-02 - Reaching the VirtualBox host-only network from WSL2

- **Goal:** confirm the control node (WSL2, NAT networking, 172.28.16.0/20) can reach lab hosts on 192.168.56.0/24.
- **Method 1:** `ping 192.168.56.1` from WSL -> **failed** (no reply).
- **Method 2:** TCP connect to port 22 on 192.168.56.21 and .22 from WSL -> **open**.
- **Conclusion:** routing via the Windows host works; the failed ping was ICMP being blocked by the Windows firewall on the host-only adapter, not a routing problem. No WSL network change (e.g. mirrored mode) was needed. Lesson: test the actual protocol (SSH) rather than ICMP.

## EXP-03 - Where to install Ansible collections

- **Goal:** install the four required collections.
- **Attempt 1:** `ansible-galaxy collection install -p ./collections ...` into the repo, which sits on the Windows drive (`/mnt/c`, 9P file share).
  - Still running after **887 s**, with 4,577 files written. Stopped.
- **Attempt 2:** same command with `-p ~/.ansible/collections` (Linux ext4 filesystem inside WSL).
  - Completed in **46 s**, 6,113 files (includes dependencies `ansible.utils` 6.1.1 and `community.library_inventory_filtering_v1` 1.1.5).
- **Conclusion:** writing many small files across the WSL/Windows boundary is roughly 20x+ slower. Collections are kept on the Linux side and pinned in `requirements.yml` (D-04).

## EXP-04 - Lab Linux servers (PXE handoff simulation)

- **Method:** `vagrant up` in `lab/` (from Windows).
- **Result:** both VMs created, booted and provisioned in **277 s** (including first download of the box). Provisioner created user `ansible`, sudo rule and authorized key only (D-06).

## EXP-05 - Phase 1 connectivity and lint checks

Raw output: `evidence/logs/20261029-150718_0*.txt`.

| Check | Command | Result |
|-------|---------|--------|
| Project config loaded | `ansible --version` | `config file = .../Ansible proofs/ansible/ansible.cfg` (confirms D-03 fix) |
| Inventory structure | `ansible-inventory --graph` | 3 hosts; function groups and site groups as designed; `switches` empty (D-08) |
| Linux ad-hoc ping | `ansible linux_servers -m ansible.builtin.ping` | `srv-main-01` and `srv-acq-01`: SUCCESS, `ping: pong`, `changed: false` |
| Full connectivity playbook | `ansible-playbook playbooks/verify_connectivity.yml` | Linux: ok=3 changed=0 on both (Ubuntu 24.04, kernel 6.8.0-86-generic, correct site groups). Router `rtr-main-01`: **failed** - `ssh connect failed: Timeout connecting to 192.168.56.10` after 30.53 s. Total run 35 s. |
| YAML style | `yamllint -s .` | 0 problems |
| Ansible best practice | `ansible-lint` (profile `production`) | Passed, 0 failures, 0 warnings, 13 files |

- **Router failure cause:** the CSR1000v VM does not exist on this laptop yet (D-07). Expected; the 30 s value equals `connect_timeout` in `ansible.cfg`.
- **Open item:** import the CSR1000v, enable SSH on it, re-run EXP-05 for `ios_devices`.

---

Experiment IDs from 2026-11-12 follow the plan's AN-xx / SD-xx scheme (AN-xx = experiment ID; requirement IDs stay B/T/S/O). Every run is captured with `evidence/scripts/run_logged.sh`, which records the command, start/end time, exit code and wall-clock time.

## EXP-06 (AN-01 re-check) - Lab restart after 14 days suspended

Raw output: `evidence/logs/20261112-193858_08_vagrant_up.txt`, `..._09_adhoc_ping_linux.txt`, `..._10_srv-acq-01_unreachable_diagnosis.txt`, `..._11_adhoc_ping_linux_after_fix.txt`.

- **Method:** `vagrant up` (both VMs were in the VirtualBox *saved/suspended* state), then `ansible linux_servers -m ansible.builtin.ping`.
- **Result 1 - failure:** `vagrant up` exited 1 after 344 s ("Timed out while waiting for the machine to boot") on `srv-acq-01`, although VirtualBox showed it `running`. Ansible: `srv-main-01` SUCCESS, `srv-acq-01` **UNREACHABLE** (`connect to host 192.168.56.22 port 22: No route to host`).
- **Investigation:** VirtualBox reported the VM running and Guest Additions reported IP 192.168.56.22, yet TCP 22 from Windows failed, while the same test to .21 passed. So the VM was "up" by the hypervisor's measure but not providing service.
- **Fix:** `vagrant reload srv-acq-01` (clean reboot of the disposable lab VM; provisioning not re-run), exit 0 in 64 s. Inside the guest, `sshd` was listening on 0.0.0.0:22, eth1 had 192.168.56.22, ufw was inactive and the guest could reach srv-main-01. The Windows ARP entry for .22 matched eth1's MAC. A TCP test immediately after the reload still failed; a re-test about a minute later passed. The early failure is attributed to the network not yet being ready, not to a second fault.
- **Result 2:** Ansible ping SUCCESS on both hosts (exit 0, 1.9 s).
- **Lesson for the design:** "VM running" ≠ "service available". Resuming saved VMs is less reliable than a cold boot, and fault monitoring must check the service (SSH/HTTP), not hypervisor state. This supports the OpenNMS service-monitoring proposal (team) and the HTTP verification tasks added in AN-02.

## EXP-07 (AN-02) - Automated configuration of both sites: Linux baseline + nginx

Raw output: `evidence/logs/20261112-195121_12_AN-02_run1_linux_servers.txt` (Ansible), `..._13_AN-02_independent_verification.txt` (checks done outside Ansible).

- **Requirement:** T1, S1, B1, B2. **Code:** `playbooks/linux_servers.yml`, `roles/linux_baseline`, `roles/web_service`, `inventory/group_vars/site_*.yml`.
- **Pre-checks:** `yamllint -s .` 0 problems; `ansible-lint` production profile passed (0 failures, 0 warnings, 31 files); `--syntax-check` on `site.yml` passed.
- **Command:** `ansible-playbook playbooks/linux_servers.yml` (from the control node, both hosts in parallel).

| Host | ok | changed | unreachable | failed | Wall time (whole run) |
|------|---:|--------:|------------:|-------:|----------------------:|
| srv-main-01 | 27 | 17 | 0 | 0 | 62.8 s |
| srv-acq-01 | 27 | 17 | 0 | 0 | (same run) |

- Slowest tasks (`profile_tasks`): baseline package install 27.3 s, nginx install 10.2 s. Everything else was under 5 s.
- **Built-in verification (part of the playbook):** `service_facts` assert nginx running + enabled; HTTP fetch on the server (127.0.0.1) **and** from the control node over the lab network (proves the ufw rule); page must contain the host's own name and site; `Server` header must not reveal the nginx version. All passed on both hosts.
- **Independent verification (outside Ansible):**
  - HTTP from the Windows host returned 200 for both servers, with headers `Server: nginx` (version hidden), `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY`. Each page names its own host and site: srv-main-01 = Main site (MAIN), srv-acq-01 = Acquired site (ACQ).
  - `sshd -T` effective settings on both hosts: `permitrootlogin no`, `passwordauthentication no`, `kbdinteractiveauthentication no`, `x11forwarding no`, `maxauthtries 3`, `banner /etc/issue.net`.
  - ufw is active with default deny inbound; only 22/tcp and 80/tcp are allowed (IPv4 and IPv6).
  - Timezone is Europe/London, the clock is synchronised, and chrony selected a UK pool source.
  - Web root is `drwxr-x--- root:www-data` and the page is `-rw-r----- root:www-data`. The unprivileged `vagrant` user got "Permission denied", which shows the permissions are enforced.
  - nginx is enabled and active; the only enabled site is `nel.conf`.
- **Result:** passed. The same playbook produced identical configuration at both sites. The only per-site differences are the intended inventory variables.
- **Limitations:** two Ubuntu VMs stand in for about 20 mixed servers. A single run says nothing yet about repeatability (AN-03) or drift (AN-04). The run time is dominated by apt downloads, so it depends on the network. No admin user accounts are managed yet (S1 is only partly covered).

## EXP-08 (AN-03) - Idempotency

Raw output: `evidence/logs/20261112-195121_12_...run1...`, `..._195622_14_AN-03_run2...`, `..._195650_15_AN-03_run3...`.

- **Requirement:** T2. **Hypothesis:** if every task declares a desired state (rather than running commands), re-running the same playbook against a host already in that state changes nothing.
- **Method:** the same command `ansible-playbook playbooks/linux_servers.yml`, run three times in a row with no other changes. Run 1 is EXP-07.

| Run | Wall time | ok (per host) | changed | failed | unreachable | Interpretation |
|----:|----------:|--------------:|--------:|-------:|------------:|----------------|
| 1 | 62.8 s | 27 | 17 | 0 | 0 | Fresh hosts: 14 tasks + 3 handlers (restart chrony, reload ssh, reload nginx) made changes |
| 2 | 26.7 s | 23 | **0** | 0 | 0 | Idempotent. 4 fewer "ok" because the handlers were not triggered (nothing changed) |
| 3 | 26.0 s | 23 | **0** | 0 | 0 | Repeatable. Same result as run 2 |

(Identical figures on both hosts in every run.)

- **Result:** passed first time. No task needed fixing. The design choices that made this work were deliberate: `cache_valid_time` on apt (no index refresh every run); templates with no timestamps or run-specific values (`index.html.j2`); `changed_when: false` on the read-only `nginx -t` check; and handlers, so services restart only when their config actually changed.
- **Analysis:** run 2 took 43 % of run 1's time, so most of the first-run cost was package installation. A no-change run still costs about 26 s for 2 hosts. That is the price of re-checking every item, and it is acceptable for scheduled compliance runs.
- **Limitation:** `changed=0` shows that Ansible *believes* the state matches. It is backed here by the verification asserts in every run, and in AN-04 by file hashes before and after.

## EXP-09 (AN-04) - Configuration drift: detection and correction

Raw output: `evidence/logs/20261112-195743_16_AN-04_drift_introduce.txt` to `..._200047_22_AN-04_final_state.txt`.

- **Requirement:** T3, S1, B3. **Method:** on `srv-acq-01` (the acquired site, where unmanaged local changes are most likely), three manual changes simulating an administrator working outside Ansible:
  1. Edited the managed web page heading ("EDITED MANUALLY").
  2. Weakened a managed security setting: `PasswordAuthentication yes` in the NEL SSH drop-in, then reloaded sshd. Confirmed live with `sshd -T`.
  3. Added an **unmanaged** firewall rule: `ufw allow 8080/tcp`.

| Step | Command / action | Result |
|---|---|---|
| Baseline | `sha256sum`, `sshd -T`, `ufw status` | page `b4e2348c…`, ssh drop-in `9b0ce30a…`, password auth **no**, rules 22 + 80 only |
| Drift | manual changes (above) | page `1e1c592b…`, drop-in `82164ada…`, password auth **yes**, extra 8080 rule |
| Detect, attempt 1 | `--check --diff` | Diffs correct for changes 1 and 2, **but the run failed on both hosts**: `object of type 'dict' has no attribute 'content'` (see below) |
| Detect, attempt 2 | `--check --diff` after fix | srv-acq-01 changed=3 (both diffs + ssh reload handler), srv-main-01 changed=0, failed=0. Change 3 **not reported** |
| Check mode is safe | state re-read | still drifted, hashes unchanged: `--check` modified nothing |
| Correct | normal run (`--diff`) | srv-acq-01 changed=3, srv-main-01 changed=0 |
| Confirm | normal run | changed=0 on both hosts |
| Final state | `sha256sum`, `sshd -T`, `ufw`, HTTP | **hashes identical to baseline**, password auth **no**, page heading restored. **8080 rule still present** |

- **Problem found and fixed (attempt 1):** `ansible.builtin.uri` is skipped in check mode, so the registered result had no `content` and the verification asserts crashed. The fix was `check_mode: false` on the two `uri` tasks: they are HTTP GETs and cannot change anything. ansible-lint production still passed. The failed run is kept as evidence (`..._17_...`).
- **Result:** drift in **managed** items was detected, shown as a line-level diff, and corrected back to byte-identical files. Drift in **unmanaged** items (an extra firewall rule) was neither detected nor removed. The playbook says "port 22 and 80 must be allowed", not "only 22 and 80 may be allowed". The test rule was removed by hand afterwards and logged.
- **Analysis / design decisions:**
  - Ansible enforces what is written in the playbook, not the complete state of the host. For security-relevant resources (firewall rules, sudoers, SSH keys) the playbook must declare the *complete* set, for example by templating the whole ufw ruleset or using exclusive modes such as `authorized_key exclusive`. Otherwise unauthorised additions persist.
  - Ansible detects drift only when it is run. Continuous drift detection would need `--check --diff` scheduled (cron or AWX/AAP job templates) with alerting on `changed>0`, or event-driven automation. This is a recommendation, not something tested here.
  - The weakened SSH setting was live, which shows the security value: a manual change re-enabling password login was reverted in one run, about 28 s.

## EXP-10 (AN-05) - Controlled failure: one site unavailable

Raw output: `evidence/logs/20261112-200116_23_AN-05_halt...` to `..._200254_26_AN-05_recovery_run_limit.txt`.

- **Requirement:** fault management (B2/T1 operational behaviour). **Method:** graceful power-off of the disposable lab VM `srv-acq-01` (`vagrant halt`), then the normal playbook against both sites. Then a cold boot (`vagrant up srv-acq-01`) and a run limited to the recovered host.
- **During the outage:**
  - srv-acq-01: `UNREACHABLE` at fact gathering after about 3 s (`connect to host 192.168.56.22 port 22: No route to host`), ok=0, unreachable=1. It was removed from the rest of the play.
  - srv-main-01: ok=23, changed=0, all verification asserts passed.
  - Playbook exit code **4** (Ansible's code for unreachable hosts). Total time 19.5 s.
- **Recovery:** cold boot completed in 47 s (exit 0). `ansible-playbook ... --limit srv-acq-01` gave ok=23, **changed=0**, failed=0. nginx was already running and the page correct after the reboot without Ansible changing anything, which shows the `enabled: true` boot persistence works.
- **Analysis:**
  - A failure at one site does not block configuration of the others. This matters for a multi-site estate where branch links fail independently.
  - Ansible reports the failure clearly (host, reason, distinctive exit code), but only at run time. It is not a monitoring system: nobody would know the site was down until the next run. This supports the team's OpenNMS proposal for fault detection, with Ansible kept for configuration.
  - Recovery is a targeted re-run (`--limit`), with no manual reconfiguration. Retry files are disabled in `ansible.cfg`, so the host must be named.
  - Compared with EXP-06, a cold boot recovered cleanly where a resume from saved state did not.
- **Limitation:** a clean power-off is the simplest failure. Partial failures (SSH up but apt mirror unreachable, disk full, a task failing mid-run) behave differently and were not tested.

## EXP-11 (AN-06 preparation) - Rebuild of srv-acq-01 and a host-key finding

Raw output: `evidence/logs/…_27_AN-06_rebuild_srv-acq-01.txt`, `…_28_AN-06_reference_hashes.txt`, `…_29_AN-06_hostkey_after_rebuild.txt`.

- **Method:**
  - Recorded the SHA-256 hashes of the five Ansible-managed files on srv-acq-01 (the reference for AN-06).
  - Rebuilt the VM with `vagrant destroy -f` + `vagrant up`, which took 52 s and returned it to the PXE-handoff state.
  - Confirmed the clean state: no chrony, no `/var/www/nel`, no SSH drop-in, timezone `Etc/UTC`, ufw inactive.
- **Expected:** a rebuilt server has a new SSH host key, so the control node (`StrictHostKeyChecking=accept-new`, D-11) should refuse it until the stale `known_hosts` entry is removed.
- **Actual:**
  - The first Ansible attempt failed with a *network timeout* (VM network not ready, as in EXP-06), so it did not test host keys.
  - A proper test, SSH with the pre-rebuild `known_hosts.old`, **succeeded with no warning**: the rebuilt VM presented the same host key.
  - `ssh-keyscan` then showed that **srv-main-01 and srv-acq-01 have identical ECDSA, ED25519 and RSA host keys** (e.g. ED25519 `SHA256:VjufUgJC…`). They are baked into the `bento/ubuntu-24.04` box and reused by every clone.
- **Analysis:**
  - Host-key checking only proves a server's identity if every server has a unique key. With cloned keys, any server built from the image can impersonate any other to the control node and to admins: a man-in-the-middle risk.
  - If Northstar's PXE pipeline deploys from a golden image, the same flaw would affect production.
  - Removing the stale `known_hosts` entry (`ssh-keygen -R`) is the normal admin step after an intentional rebuild. Here it was not even needed, which is itself the symptom.
- **Design decision / recommendation:**
  - Host keys must be regenerated on first boot, as part of the PXE/autoinstall stage, *before* the Ansible handoff (e.g. remove `/etc/ssh/ssh_host_*` in the image and run `ssh-keygen -A` / cloud-init on first boot).
  - Raise this with Jack (PXE owner) as a change to the D-06 handoff contract.
  - Not fixed in this lab, to keep the AN-06 starting point identical to AN-02. Recorded as a security limitation of the PoC.

## EXP-12 (AN-06) - Manual configuration vs Ansible

Raw output: `evidence/logs/20261112-215000_32_AN-06_manual_session_transcript.txt` (operator transcript), `…_30_AN-06_manual_build_state.txt` (state after manual build), `…_31_AN-06_manual_build_check_diff.txt` (Ansible consistency check), reference hashes `…_28_…`. Runbook: `docs/AN-06_manual_procedure.md`.

- **Requirement:** T5, B1 (reduce manual effort and error). **Question:** what does it cost a person to reach the *same* end state by hand, and how sure can they be that they got it right?
- **Method:**
  - The author (Yassine) configured the freshly rebuilt `srv-acq-01` by hand, following the 15-step runbook.
  - Copy-pasting from the runbook was allowed (best case for manual work).
  - Afterwards, the result was compared with the Ansible-built reference using SHA-256 of the five managed files plus `ansible-playbook … --check --diff --limit srv-acq-01`. That check changes nothing.

| Measure | Manual (1 server) | Ansible (AN-02 first run) |
|---|---|---|
| Elapsed time | **~15 min** (operator stopwatch). VM timestamps: login 21:49:50, Step 13 file at 22:09 UTC | **62.8 s for both servers in parallel** |
| Operator actions | 15 runbook blocks, 29 command lines, plus 1 repeated block (Steps 7–8 re-done) | 1 command |
| Errors seen by the operator | 2 × `-bash: You: command not found`, from accidentally pasting instruction text with the commands (Steps 8 and 13) | 0 |
| Unnecessary rework | Steps 7–8 repeated, because the error made a successful step look failed | 0 |
| Verification | **Not performed.** Step 15 was skipped and the operator finished unsure whether problems remained | Automatic every run: service state, HTTP on-host and over the network, page identity, header check |
| End-state consistency | **Identical:** all 5 file hashes match the reference; owners/modes, packages, services, timezone, sshd and ufw match; Ansible `--check` reported ok=23 changed=0 | Identical by construction (AN-03: changed=0) |
| Scaling (estimate, not measured) | About 15 min × N servers, sequential, with the error chance repeated N times | Parallel (`forks = 10`); per-run time grows slowly with N |

- **Result:**
  - The manual build was **correct**, byte-identical to Ansible's.
  - It took about **14× longer** for one server than Ansible took for two.
  - It produced **two misleading error messages** and **one unnecessary repeat**, and ended **without verification**: the operator reported "problems I couldn't fix" although none remained. Only the automated check afterwards showed the server was right.
- **Analysis:**
  - The main difference is not correctness. A careful person with a precise runbook can be exactly right. The differences are **effort, confidence and evidence**.
  - Manual work gives no reliable signal of success. A copy-paste slip produced error text next to a success message, and the operator could not tell them apart. Ansible reports per task (ok/changed/failed) and asserts the outcome.
  - At Northstar's scale (about 20 servers, more after acquisitions), manual time and error exposure grow with every server. Ansible's run cost grows slowly because hosts run in parallel.
  - The manual run was *easier* than real life: the runbook was derived from the Ansible templates, and the values were pre-filled for this host.
- **Fairness and limitations (must be stated in the report):**
  - n = 1 manual run by one operator, who is also the author and already knew the configuration.
  - Copy-paste from a runbook is a best case. Typing from documentation would be slower and more error-prone.
  - **Development effort is not included:** writing and testing the two roles took far longer than one manual build. The roles were developed with AI assistance in this project, so their development time does not represent an engineer writing them unaided and is not used as a figure. Automation only pays back once the same configuration is applied repeatedly: more servers, rebuilds (AN-06 itself), drift correction (AN-04). It does not pay back for a one-off change on one server.
  - The scaling row is reasoning, not measurement.
  - Instruction text was pasted because expected-output notes sat directly next to the commands in the operator's instructions. That is a runbook-design weakness in itself: runbooks are error-prone documents too.
- **Design decision:**
  - Use Ansible for repeatable server configuration and verification at both sites (B1, T1, T2).
  - Keep manual changes for one-off investigation only, followed by a `--check --diff` run to detect the resulting drift (AN-04).

## EXP-13 - AN-08: fully managed host firewall (S1, T3) - DONE 13 Nov 2026

- **Goal:** close the AN-04 limitation (an unmanaged `ufw allow 8080/tcp` survived correction). The approved policy is deny inbound and allow outbound, with only 22/tcp (SSH) and 80/tcp (web) open; Ansible deletes anything else.
- **Design:** `roles/linux_baseline/tasks/firewall.yml`. Approved rules are listed in `group_vars/linux_servers.yml`.
  - The play asserts that SSH is in the approved list before doing anything (lock-out guard).
  - Approved rules and default deny are applied first.
  - `ufw show added` is then compared with the approved list, and only the rules outside it are deleted.
  - In `--check` mode the unapproved rules are reported as a change.
  - "routed" is not managed: with forwarding off, ufw reports it as "disabled", and the module would report a change on every run (T2).
- **Safety:** approved by the user before running.
  - VirtualBox snapshots `pre-AN08-10` of both VMs were taken first (log 35b).
  - srv-acq-01 was done first as the canary.
  - A rule existed to stop at the first UNREACHABLE.
  - Plan and recovery: `docs/AN-07-10_PLAN.md` §1.
- **Pre-checks (no changes):**
  - log 33: state before the change.
  - log 34: new code in `--check` on today's rules gave **changed=0** on both hosts, so the parser treats existing rules as approved.
- **Method and result:**

| Step | Log | Result |
|---|---|---|
| Plant 2 unapproved rules (`8080/tcp`, `3306/tcp from 192.168.56.0/24`) and a temporary listener on 8080 | 36 | both rules present |
| Probe 8080 from the control node | 37 | `http 200` (reachable) |
| `--check --diff` | 38 | exactly the 2 planted rules reported "would be removed"; changed=1, nothing altered |
| Apply on srv-acq-01 | 39 | both rules deleted; ok=29 changed=1, 65.5 s |
| Verify (new SSH session, ufw, probes) | 40 | fresh SSH OK; only 22/tcp and 80/tcp remain; **8080 → `000` (blocked)**, 80 → `200` |
| Apply to both servers | 41 | changed=0 on both |
| Rerun | 42 | changed=0 on both (idempotent) |
| Stop test listener | 43 | inactive |

- **Analysis:** Ansible now enforces the whole firewall state, not just the rules it added. A rule someone adds by hand is reported by `--check` and removed on the next run. SSH access was never interrupted.
- **Limitations:**
  - The approved list is the same for every Linux server. Per-role ports would need group or host variables.
  - Rules are compared exactly as ufw prints them, so a rule that matches an approved one except for its comment counts as unapproved. It is deleted, and the approved one is re-added on the same run.
  - Console recovery (`vagrant`/`vagrant` login) was documented but not tested.

## EXP-14 - AN-09: unique SSH host keys (S1, T4) - DONE 13 Nov 2026

- **Goal:** fix the EXP-11 finding. Both VMs shared the public bento box's host keys (ED25519 `SHA256:VjufUgJC…Enlc`), so anyone holding the box could impersonate either server.
- **Design:** `playbooks/rotate_host_keys.yml`.
  - **Play 1 (read-only):** compares fingerprints across the group and flags shared keys.
  - **Play 2:** runs only with `-e hostkey_rotate=true`, one server at a time (`serial: 1`, `max_fail_percentage: 0`). For each server it:
    1. backs up the keys to `/root/ssh-hostkey-backup/` and backs up the control node's `known_hosts`;
    2. deletes the keys and runs `ssh-keygen -A`, then `sshd -t`, then **reloads** ssh. A rescue block restores the old keys if this step fails.
    3. reads the new public key over the existing authenticated session and writes it to `known_hosts`, so it is not trusted blindly from the network;
    4. closes the connection and reconnects with host-key checking.
  - `authorized_keys` is never touched.
- **Safety:** approved by the user. Snapshots `pre-AN08-10`. Plan and recovery: `docs/AN-07-10_PLAN.md` §2.

| Step | Log | Result |
|---|---|---|
| Detect only | 35 | both hosts **SHARED** (same ED25519 fingerprint) |
| Rotate | 44 | srv-main-01 then srv-acq-01: ok=17 changed=7 each; reconnect (`ping`) succeeded on both; 47.6 s |
| Strict host-key SSH to both | 45 | both connect; new keys `root@srv-main-01` (ED25519 `SHA256:L+6UdFrN…wj/Y`) and `root@srv-acq-01` (ED25519 `SHA256:7DQvT/tK…C05o`) - all 3 key types now differ |
| Connect using the pre-rotation known_hosts | 46 | **refused**: "REMOTE HOST IDENTIFICATION HAS CHANGED", exit 255 (expected: the old key is no longer valid) |
| Rerun with rotation enabled | 47 | both "unique", changed=0 (idempotent: nothing to rotate) |
| `vagrant ssh <vm> -c hostname` | 48 | both work (out-of-band recovery path intact) |

- **Analysis:** shared host keys can be detected and fixed automatically without losing management access. The key is accepted on the control node from the authenticated session, which is stronger than trust-on-first-use. The real fix belongs at build time, in Jack's PXE first-boot `ssh-keygen -A`. This playbook is the remediation for servers that already exist, and a check that can run regularly.
- **Notes:**
  - `known_hosts.pre-rotation-srv-acq-01` was saved after srv-main-01 had already been rotated, so it holds srv-main-01's new key and srv-acq-01's old key. This is correct for the negative test.
  - The key backups in `/root/ssh-hostkey-backup/` hold the publicly known bento private keys. They were left in place for rollback; deleting them is a separate step that needs approval.

## EXP-15 - AN-10: repeated drift detection and correction (T2, T3, S1) - DONE 13 Nov 2026

- **Goal:** show that AN-04 (one drift and correction) and AN-03 (idempotency) hold up when repeated, now that the firewall is fully managed (EXP-13).
- **Method:** `evidence/scripts/drift_cycles.sh 3`, run on both servers, 01:38-01:48 UTC, approved by the user. Each cycle made the same 5 manual changes:
  1. an extra NTP server in `chrony.conf`;
  2. `MaxAuthTries 6` in the sshd drop-in (file only);
  3. an edit to the web page;
  4. chrony disabled at boot;
  5. an unapproved `ufw allow 8080/tcp`.

  It then ran `--check --diff`, the correcting run, a second run and a read-only verification.
- **Result** (`20261113-013830_AN-10_drift_cycles_summary.csv`, `_verdict.txt`, 15 logs `*_AN-10_c{1,2,3}_*`):

| Cycle | Detect (check mode) changed | Correct changed | Rerun changed | Exit codes | Verdict |
|---|---|---|---|---|---|
| 1 | 14 | 14 | 0 | all 0 | PASS |
| 2 | 14 | 14 | 0 | all 0 | PASS |
| 3 | 14 | 14 | 0 | all 0 | PASS |

  - Times: detect 53.8-58.2 s, correct 67.8-74.2 s, rerun 61.8-65.1 s, for both servers in parallel.
  - The final verification on both servers showed:
    - `maxauthtries 3`;
    - chrony `enabled`;
    - only 22/tcp and 80/tcp in ufw (the 8080 rule was removed each cycle, which closes the AN-04 limitation);
    - HTTP 200.
  - The `chrony.conf` and sshd drop-in hashes are identical on both servers and match the AN-06 reference (log 28). srv-acq-01's `index.html` hash also matches log 28. srv-main-01's page has no earlier reference hash, so it was not compared.
- **Analysis:**
  - Detection and correction were identical in every cycle: 7 changes per server, all 5 drifts plus the 2 handlers (chrony restart, ssh reload).
  - The second run was always changed=0.
  - Check mode reported all 5 drift types, including the firewall rule, without changing anything.
- **Limitations:**
  - The same drift set was used each cycle (repeatability, not coverage).
  - n = 3 cycles on 2 lab VMs.
  - Drift was introduced with root access via Ansible ad-hoc commands; a real attacker could also tamper with Ansible's own access.

## EXP-16 - AN-07: Ansible on a real Cisco IOS XE device via the DevNet sandbox (T1, T2, T3) - ATTEMPTED, BLOCKED (not executed) 13 Nov 2026

- **Goal:** prove the network-device half of T1 with the smallest reversible change. Set one interface description with `cisco.ios`, verify it on the device, rerun to show changed=0, then roll back and verify again.
- **Why the DevNet sandbox:** the lab router `rtr-main-01` (CSR1000v) was never available (D-07, EXP-05).
- **Prepared (ready to run, lint-clean, production profile):**
  - `inventory/devnet_iosxe.yml`: a separate inventory, so no NEL playbook can reach a third-party device by accident. Credentials come only from environment variables. Uses paramiko, because ansible-pylibssh is not installed.
  - `playbooks/iosxe_interface_description.yml` runs in three phases:
    - *precheck* (read-only): version, privilege 15 check, interfaces, running-config backup;
    - *change*: records the original description once and never overwrites it, sets the test description with `cisco.ios.ios_interfaces`, then verifies on the device;
    - *rollback*: restores the original, or removes the test description if there was none, then verifies on the device.
  - Before and after every phase, full running-configs are saved to the gitignored `evidence/iosxe/raw/`, plus a sanitised diff.
  - `evidence/scripts/run_iosxe.sh` runs one phase as a logged run. `evidence/scripts/set_iosxe_password.sh` lets the user type the password straight into `~/.iosxe_env` (mode 600), without echo.
- **What happened:**

| Time (UTC) | Step | Result | Evidence |
|---|---|---|---|
| 01:05 | Reachability probe (no login) | `devnetsandboxiosxec8k.cisco.com` resolves; tcp/22, 443, 830 open | plan §0 |
| 01:44 | Sandbox launched (6 h session) from the student's signed-in DevNet account - the **AI assistant clicked "Launch" in the student's Chrome at his request**; page shows host, username and a generated password | Sandbox "Running", IOS XE 17.12.02 | SS16 |
| 01:56 | Precheck run 1 | **Authentication failed**. Cause found: the saved password was 117 characters (wrong clipboard content) | `20261113-015617_AN-07_precheck.txt` |
| 01:58 | Precheck run 2 (password re-typed, 13 characters) | **Authentication failed** | `20261113-015844_AN-07_precheck.txt`; SS15 |
| ~02:00 | Diagnosis without sending a password (`ssh -v`, auth method `none`) | Server `Cisco-1.25` offers `publickey,keyboard-interactive,password`; username matches the page | session notes |
| ~02:01 | Student's own manual `ssh 0yassl40@…` | 3 keyboard-interactive prompts + 1 password prompt, then "Connection closed" (rejected) | student's terminal output, pasted into the session |
| ~02:07 | Student ended the session and launched a new one himself (new password) | New password rejected in the student's manual SSH. Later re-test with the current password also rejected | student report |

- **Result:** **not executed.** No configuration was sent to any device. The precheck stopped at login, before any command ran.
- **Stopped deliberately:**
  - No password guessing against a third-party system.
  - No more automated attempts after two failures (lockout risk).
  - Passwords were typed by the student; the assistant never entered or used them.
- **Cause:** the device rejected the per-session credentials generated by the DevNet portal. Our side was tested: reachability, auth methods offered, username, password length, and a manual login outside Ansible. **Not found:** the reason on Cisco's side, which may be provisioning or the shared device being reset. The October attempt with the old static credentials failed in the same way (EXP-01).
- **Analysis:**
  - Lab dependency is a real project risk. All three third-party Cisco labs used in this project limited the work:
    - IOS XE: login rejected (EXP-01, EXP-16);
    - SD-WAN: read-only, with an expired certificate (SD-01);
    - CSR1000v image: unavailable (EXP-05).
  - Network-device automation for Northstar should be proven on equipment the organisation controls, such as Cisco Modeling Labs or a spare lab router, before production use.
- **Requirement impact:**
  - T1: Linux part demonstrated; network-device part **still not demonstrated**, so T1 stays *partly addressed*.
  - S2 and O2: unchanged (not attempted).
  - The playbook is ready to run in about 5 minutes once a working login exists: `run_iosxe.sh precheck`, then `change <if>` twice, then `rollback <if>`.
