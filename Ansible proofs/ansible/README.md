# NEL configuration management PoC (Ansible)

COM615 - Northstar Engineering Ltd consultancy. Ansible workstream (Yassine).

Applies a repeatable, version-controlled configuration to Linux servers and Cisco IOS devices across NEL's main and acquired sites, from one inventory.

## Layout

```
ansible.cfg                 project settings (inventory, vault file, logging, timing callbacks)
requirements.yml            pinned Ansible collections
requirements-dev.txt        pinned Python tools for the control node
inventory/
  hosts.yml                 groups by function and by site
  group_vars/all/vars.yml   settings shared by every device
  group_vars/all/vault.yml  ENCRYPTED secrets (ansible-vault)
  group_vars/linux_servers.yml, ios_devices.yml   how to connect to each device type
  host_vars/<host>.yml      per-host address and role
playbooks/                  site.yml (everything) + one playbook per job
roles/                      linux_baseline, monitoring_agents, ios_baseline (later phases)
control-node/               script + WSL config that build the Ansible control node
lab/Vagrantfile             2 Ubuntu VMs that simulate freshly PXE-built servers
evidence/                   logs, diffs and timings from real runs
docs/                       DECISIONS.md, EXPERIMENTS.md, REQUIREMENTS.md
```

## Lab

| Host | Address | Groups | Platform |
|------|---------|--------|----------|
| srv-main-01 | 192.168.56.21 | linux_servers, site_main | Ubuntu 24.04 (Vagrant VM) |
| srv-acq-01 | 192.168.56.22 | linux_servers, site_acquired | Ubuntu 24.04 (Vagrant VM) |
| rtr-main-01 | 192.168.56.10 | ios_devices, routers, site_main | Cisco CSR1000v IOS XE (pending import) |

## Set up a control node (WSL Ubuntu 24.04)

The whole control node is rebuilt by one script, kept in this repo:

```powershell
wsl --install -d Ubuntu-24.04          # Windows, once
```
```bash
cd "/mnt/c/Users/<you>/Com-615-group-respository/Ansible proofs/ansible"
bash control-node/setup_control_node.sh
```

It installs OS packages, applies [control-node/wsl.conf](control-node/wsl.conf) (D-03), creates the
venv from `requirements-dev.txt`, installs collections from `requirements.yml`, creates the SSH key
and checks for the vault password file. Output of a real run: `evidence/logs/*_07_setup_control_node.txt`.

Kept **out of the repo on purpose** (it is public): the private key `~/.ssh/nel_ansible_ed25519` and the
vault password `~/.ansible/nel_vault_pass`. Get the vault password from the project owner.

## Start the lab servers (Windows PowerShell)

```powershell
cd "Ansible proofs\ansible\lab"
vagrant up
```

## Run

```bash
cd "Ansible proofs/ansible"
ansible-inventory --graph                          # show the inventory
ansible linux_servers -m ansible.builtin.ping      # ad-hoc reachability test
ansible-playbook playbooks/verify_connectivity.yml # Linux ping + IOS facts
ansible-playbook playbooks/site.yml                # everything
yamllint -s . && ansible-lint                      # quality checks
```

## Secrets

- `inventory/group_vars/all/vault.yml` is encrypted with ansible-vault (AES256).
  View/edit: `ansible-vault view|edit inventory/group_vars/all/vault.yml`.
- The vault password file `~/.ansible/nel_vault_pass` is outside the repo. **This repository is public.**
- `lab/control_node.pub` is a *public* key (safe to share); the private key stays in `~/.ssh/`.
