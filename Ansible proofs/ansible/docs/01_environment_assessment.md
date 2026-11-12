# 01 - Environment assessment (Ansible Phase 1 + Cisco Catalyst SD-WAN Phase 2)

Assessed 2026-11-12 on the author's laptop. Read-only inspection; the only changes made were starting the existing lab VMs (see EXP-06).

## 1. Host machine

| Item | Finding | Relevance |
|---|---|---|
| OS | Windows 11 Pro 10.0.26300, 64-bit | Ansible cannot run natively on Windows as a control node → WSL2 needed |
| CPU | AMD Ryzen 9 5900HS, 8 cores / 16 threads, hardware virtualisation enabled | Enough for 2–3 small VMs in parallel |
| RAM | 31.4 GB total (17.9 GB free at inspection) | Linux VMs at 1 GB each are trivial; a full SD-WAN controller stack is not (see §4) |
| Disk | 268 GB free of 476 GB on C: | No constraint |
| Hypervisor | Hyper-V active (`HypervisorPresent=True`, needed by WSL2 and Docker Desktop); VirtualBox 7.2.16 running on top of it | Works, but VMs run through the Hyper-V backend. One VM failed to resume cleanly from a saved state (EXP-06) |
| WSL | Ubuntu-24.04 (WSL2), docker-desktop (WSL2) | Ubuntu-24.04 is the Ansible control node |
| Tools | Vagrant 2.4.9, Git, Windows OpenSSH, Python 3.12, Docker Desktop | Vagrant gives a reproducible lab (`lab/Vagrantfile`) |
| Networks | Wi-Fi (Internet), VirtualBox host-only 192.168.56.0/24, WSL vEthernet (NAT) | WSL reaches the host-only network through Windows routing. ICMP is blocked by the host firewall but TCP works (EXP-02) |

## 2. Ansible environment (already built, Phase 0–1, commit `40bf3fb`)

| Component | Detail |
|---|---|
| Control node | WSL Ubuntu 24.04, Python venv `~/.venvs/ansible`, ansible-core 2.21.5, ansible-lint 26.10.1, yamllint 1.38.0; rebuild script `control-node/setup_control_node.sh` |
| Collections | Pinned in `requirements.yml` and installed on the Linux filesystem (EXP-03): cisco.ios 11.6.0, ansible.netcommon 8.7.1, ansible.posix 2.2.2, community.general 13.5.0 |
| Secrets | Ansible Vault (AES256). Vault password file and SSH private key live outside the repo |
| Managed nodes | `srv-main-01` 192.168.56.21 (site_main), `srv-acq-01` 192.168.56.22 (site_acquired): Ubuntu 24.04, 1 vCPU / 1 GB, user `ansible` with key auth and sudo (the PXE handoff state, D-06) |
| Network device | `rtr-main-01` (CSR1000v, 192.168.56.10) is defined but **not available**: no image imported (D-07) |

**Chosen approach:** keep this environment. It already meets the AN-01 prerequisites and is reproducible from the repo. Docker containers were considered as lighter managed nodes, but they were rejected for this PoC: containers do not run systemd, sshd and ufw the way a real server does, which would weaken the SSH-hardening, firewall and service tests.

**Limitations:**
- Two VMs stand in for about 20 servers, and both are on the same host-only network. There is no real WAN between the "sites".
- There are no switches, and the router is missing, so network-device automation (AN-07) is blocked until an IOS XE image or a teammate's device is available.
- VirtualBox running on Hyper-V is slower, and resuming saved VMs was unreliable (EXP-06). Shutting down and cold-booting is preferred.

## 3. Resource needs of the Ansible lab

| Item | Use |
|---|---|
| 2 × Ubuntu VMs | 2 GB RAM, 2 vCPU, about 6 GB disk (linked clones) |
| Control node | WSL, under 1 GB RAM in use |
| Optional Cat8000v/CSR1000v | About 4 GB RAM, 2 vCPU, needs a licensed image (NetAcad/CML or Cisco account). Not available |

## 4. SD-WAN environment

A local Cisco Catalyst SD-WAN lab is **not feasible** on this machine:
- SD-WAN Manager, Controller and Validator images need a Cisco software entitlement.
- SD-WAN Manager on its own is specified for far more RAM than the free memory here.
- A minimum overlay also needs at least two WAN Edge routers.

The practical SD-WAN work will therefore use a **Cisco DevNet sandbox** accessed over the Internet. Experiment SD-01 will record which sandbox, software version, access method, permissions and limitations actually apply on the day; nothing is assumed here. Access needs the author's own Cisco account. Credentials will be kept in environment variables only and never written to the repo.

Local requirements for SD-WAN API work: Python 3.12, which is present, plus `requests` in a dedicated virtual environment. That is a small install and needs approval.

## 5. Summary of decisions

| Decision | Reason |
|---|---|
| Keep WSL2 + VirtualBox/Vagrant lab | Already working and reproducible. Real systemd/sshd/ufw behaviour |
| No containers as managed nodes | Would not test SSH hardening, firewall or service management realistically |
| SD-WAN via DevNet sandbox | Licensing and RAM rule out a local controller stack |
| Cold-boot VMs instead of resuming saved state | EXP-06 resume failure |
