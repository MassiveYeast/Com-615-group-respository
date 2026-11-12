# Screenshot checklist for the report (Ansible, Phase 1)

The brief says screenshots must show **what was investigated, what happened and what was learned**, not just that a command was typed (Assessment Overview, §6). So each screenshot below has a purpose, a caption and the report section it supports. Keep the figure count small: the ★ items are the essential ones; the rest are appendix or backup.

## How to take them honestly

- **Option A (preferred): re-run live.** Every command below is safe to re-run. A live re-run creates a **new** log in `evidence/logs/`; keep it and use its timestamp in the caption. A re-run screenshot is genuine evidence of a repeat of the experiment, not the original run, so say "repeat run on <date>" if the numbers differ.
- **Option B: open the saved original log** (`evidence/logs/<file>`) in VS Code and screenshot the relevant lines. Put the filename in the caption.
- Never edit output, crop out failures, or combine outputs from different runs into one image.
- Before screenshots: make the terminal readable (font 14+, dark-on-light or light-on-dark, wide window so lines do not wrap), and crop to the relevant lines.
- Commands are run from WSL in the project folder:
  ```bash
  cd "/mnt/c/Users/yassi/Com-615-group-respository/Ansible proofs/ansible"
  source ~/.venvs/ansible/bin/activate
  ```
  VM commands (`vagrant ...`) are run from PowerShell in `Ansible proofs\ansible\lab`.

## Checklist

| ✓ | Fig | Experiment | What the screenshot must show | How to produce it | Original evidence | Report section |
|---|---|---|---|---|---|---|
| ☐ | ★1 | Topology | Lab diagram: control node (WSL) → srv-main-01 (site_main) and srv-acq-01 (site_acquired), router pending | Diagram (draw.io), not a screenshot | `inventory/hosts.yml` | 6 (PoC environment) |
| ☐ | 2 | AN-01 | Inventory grouped by function **and** site | `ansible-inventory --graph` | `…150718_02_inventory_graph.txt` | 6 |
| ☐ | 3 | AN-01 / EXP-06 | The fault: srv-acq-01 UNREACHABLE while VirtualBox says "running" | Original log only (cannot be reproduced on purpose) | `…194520_09_adhoc_ping_linux.txt` + `…194535_10_…diagnosis.txt` | 6 (unsuccessful test → lesson) |
| ☐ | ★4 | AN-02 | First run PLAY RECAP: ok=27 changed=17 failed=0 on both hosts + run time | Original log (first runs cannot be repeated without a rebuild) | `…195121_12_AN-02_run1_linux_servers.txt` | 6 |
| ☐ | 5 | AN-02 | Verification asserts passing ("nginx running and enabled", "serves its own page") | `ansible-playbook playbooks/linux_servers.yml`, scroll to the verify tasks | same as 4 | 6 |
| ☐ | ★6 | AN-02 | Both identification pages side by side in a browser (http://192.168.56.21 and .22) showing different site values from one playbook | Browser on Windows | `…195237_13_AN-02_independent_verification.txt` | 6 (consistency + per-site variables) |
| ☐ | 7 | AN-02 | Independent check: `sshd -T` (root/password login off) and `ufw status verbose` | `vagrant ssh srv-main-01` then `sudo sshd -T \| grep -E '^(permitrootlogin\|passwordauthentication) '; sudo ufw status verbose` | same as 6 | 6 / 2 (security management) |
| ☐ | ★8 | AN-03 | Run 2 PLAY RECAP: **changed=0** on both hosts (put next to Fig 4, or make a table figure of runs 1–3) | `ansible-playbook playbooks/linux_servers.yml` | `…195622_14…run2…`, `…195650_15…run3…` | 6 |
| ☐ | ★9 | AN-04 | `--check --diff` output showing the `-PasswordAuthentication yes / +PasswordAuthentication no` and page heading diffs | Re-do drift (commands in EXP-09) then `ansible-playbook playbooks/linux_servers.yml --check --diff` | `…195913_18…rerun.txt` | 6 |
| ☐ | 10 | AN-04 | The check-mode **failure** ("no attribute 'content'") as an honest troubleshooting example | Original log only | `…195808_17…check_diff.txt` | 6 / appendix |
| ☐ | ★11 | AN-04 | Final state: hashes back to baseline **and** the 8080 rule still present (the limitation) | Original log | `…200047_22_AN-04_final_state.txt` | 6 + 7 (limitation → recommendation) |
| ☐ | ★12 | AN-05 | Run with srv-acq-01 down: UNREACHABLE for acq, srv-main-01 completes, exit 4 | `vagrant halt srv-acq-01`, run playbook, then `vagrant up srv-acq-01` | `…200133_24…site_down.txt` | 6 / 2 (fault management) |
| ☐ | 13 | AN-05 | Recovery run `--limit srv-acq-01` changed=0 | `ansible-playbook playbooks/linux_servers.yml --limit srv-acq-01` | `…200254_26…recovery…` | 6 |
| ☐ | ★14 | AN-06 | Results table: manual vs Ansible (time, steps, errors, consistency) | Table figure built from the AN-06 results, not a screenshot | AN-06 logs (to be created) | 6 |
| ☐ | 15 | AN-06 | The consistency check of the manual build (`--check --diff` / hash comparison) | Produced during AN-06 | AN-06 logs | 6 |
| ☐ | 16 | Quality | `ansible-lint` production profile passed + `yamllint` clean | `ansible-lint; yamllint -s .` | lint runs in session | 3 / appendix (code quality) |
| ☐ | 17 | Ownership | GitHub commit history showing your commits (`40bf3fb`, `669f2c6`, …) | GitHub web UI → Commits, filtered by author | git log | 3 (individual contribution) |

## After taking them

- Save images in `evidence/screenshots/` named `figNN_<short-name>.png` (e.g. `fig08_AN-03_run2_changed0.png`).
- Give each a caption in the report: "Figure N – <what it shows> (source: `evidence/logs/<file>`)", and **discuss it in the text**. A figure that is never referred to is weak evidence.
- Tick the box above and commit the images.
