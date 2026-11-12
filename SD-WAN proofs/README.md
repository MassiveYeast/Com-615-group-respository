# SD-WAN proofs - Cisco Catalyst SD-WAN (Phase 2, Week-6 Requirement 2)

Owner: Yassine Lasraoui. Experiments SD-01..SD-06 and INT-01. The Ansible work (Phase 1) is in `../Ansible proofs/ansible/`.

| Path | Contents |
|---|---|
| `scripts/sdwan_client.py` | Read-only SD-WAN Manager REST client (inventory, overlay state, policy objects) |
| `scripts/run_client.sh` | Runs the client from WSL and saves the console output to `evidence/logs/` |
| `docs/EXPERIMENTS.md` | SD-01..SD-06 write-ups (environment, results, analysis) |
| `evidence/logs/` | Raw console output, timestamped (UTC) |
| `evidence/api/` | Sanitised JSON responses from the API |

## Running the client

Credentials are **never** stored in the repo. Put them in `~/.sdwan_env` in WSL (`chmod 600`):

```bash
export SDWAN_HOST=sandbox-sdwan-2.cisco.com
export SDWAN_USER=<from the DevNet sandbox page>
export SDWAN_PASS=<from the DevNet sandbox page>
export SDWAN_PIN_SHA256=<certificate fingerprint, see docs/EXPERIMENTS.md SD-01>
```

Then: `bash scripts/run_client.sh 10_SD-02_inventory all`

One-off setup: `python3 -m venv ~/.venvs/sdwan && ~/.venvs/sdwan/bin/pip install requests==2.32.3`
