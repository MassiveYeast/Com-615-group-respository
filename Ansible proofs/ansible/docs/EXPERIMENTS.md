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
- **Method:** TCP tests from Windows to `devnetsandboxiosxe.cisco.com` and `devnetsandboxiosxec8k.cisco.com` on ports 22/443/830; SSH login from WSL with the previously published credentials (`admin` and `developer`, password `C1sco12345`).
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
