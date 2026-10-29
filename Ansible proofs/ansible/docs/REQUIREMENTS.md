# Requirements traceability

Client requirement (Ansible workstream):

> "Demonstrate an inventory and playbook capable of applying a repeatable configuration to multiple systems (switches, routers and Linux servers) and explain the significance of idempotency."

Status key: **Done** = implemented and evidenced; **Partial**; **Pending**.

| # | Requirement | FCAPS area | Artefact | Evidence | Status |
|---|-------------|-----------|----------|----------|--------|
| R1 | One inventory describing all managed systems at both sites | Configuration | `inventory/hosts.yml`, `host_vars/`, `group_vars/` | `ansible-inventory --graph` (EXP-05) | Done |
| R2 | Control node can reach and authenticate to Linux servers | Configuration | `group_vars/linux_servers.yml`, `playbooks/verify_connectivity.yml` | EXP-05 ping + playbook | Done |
| R3 | Control node can reach and authenticate to routers | Configuration | `group_vars/ios_devices.yml`, `playbooks/verify_connectivity.yml` | EXP-05 (currently failing: no device) | Pending - CSR1000v |
| R4 | Switches covered by the same inventory and playbooks | Configuration | `switches` group | Inventory graph | Partial - group defined, no lab device (D-08) |
| R5 | Repeatable baseline applied to multiple Linux servers | Configuration / Security | `roles/linux_baseline` | - | Pending (Phase 2) |
| R6 | Repeatable baseline applied to IOS devices | Configuration / Security | `roles/ios_baseline` | - | Pending |
| R7 | Idempotency demonstrated (second run reports `changed=0`) | Configuration | baseline playbooks | - | Pending |
| R8 | Drift detection (check/diff mode) | Configuration | `--check --diff` runs, `evidence/diffs/` | - | Pending |
| R9 | Network configuration backups under version control | Configuration | `playbooks/backup_network_configs.yml` | - | Pending |
| R10 | New PXE-built server brought to baseline automatically | Configuration | `playbooks/bootstrap_new_server.yml`, PXE handoff (D-06) | - | Pending |
| R11 | Enforced SSH hardening, managed users | Security | `linux_baseline`, `ios_baseline` | - | Pending |
| R12 | SNMPv3 on network devices | Security / Performance | `ios_baseline` | - | Pending |
| R13 | No secrets in plain text in the repository | Security | `group_vars/all/vault.yml` (AES256), `.gitignore`, D-10 | `head -1 vault.yml` = `$ANSIBLE_VAULT;1.1;AES256` | Done |
| R14 | Timing data for Manual CLI vs RESTCONF vs Ansible comparison | Performance (of the method) | `profile_tasks`/`timer` callbacks, `evidence/timings/` | Callbacks active (EXP-05 shows per-task times) | Partial |
| R15 | Code quality checked automatically | - | `.yamllint`, `.ansible-lint` | EXP-05: both pass | Done |
