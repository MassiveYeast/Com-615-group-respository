# AN-06 - Manual configuration runbook (for the manual vs Ansible comparison)

**Purpose:** measure what it costs a person to produce, by hand, exactly the same end state that `playbooks/linux_servers.yml` produces. Then compare time, number of steps, errors, verification effort and consistency (requirement T5, B1).

**Fairness rules (keep these, and state them in the report):**
1. The target is the freshly rebuilt `srv-acq-01` (clean PXE-handoff state, the same starting point Ansible had in AN-02).
2. You may **copy-paste** each block from this runbook. This is the *best case* for manual work: a well-written runbook, no typing errors from retyping. Real manual work without a runbook would be slower.
3. Start the stopwatch when you press Enter on Step 1. Stop it when Step 15 shows the expected output.
4. Do every step in order, even if you think it is not needed. If something fails, fix it and **write down what happened** (that is data, not a failure of the experiment).
5. Do not run Ansible against `srv-acq-01` until you have finished and filled in the timing sheet.

---

## Step 0 - Log in (not timed)

In PowerShell:

```powershell
cd "C:\Users\yassi\Com-615-group-respository\Ansible proofs\ansible\lab"
vagrant ssh srv-acq-01
```

You are now `vagrant@srv-acq-01` with sudo. **Start the stopwatch on Step 1.**

---

## Step 1 - Refresh the package index
```bash
sudo apt-get update
```

## Step 2 - Install packages
```bash
sudo apt-get install -y chrony ufw curl nginx
```

## Step 3 - Set the timezone
```bash
sudo timedatectl set-timezone Europe/London
```

## Step 4 - Configure NTP (chrony)
```bash
sudo tee /etc/chrony/chrony.conf > /dev/null <<'EOF'
# Ansible managed
# NEL time synchronisation - sources come from inventory/group_vars/all/vars.yml
pool 0.uk.pool.ntp.org iburst
pool 1.uk.pool.ntp.org iburst

driftfile /var/lib/chrony/chrony.drift
makestep 1.0 3
rtcsync
logdir /var/log/chrony
EOF
sudo chown root:root /etc/chrony/chrony.conf && sudo chmod 0644 /etc/chrony/chrony.conf
```

## Step 5 - Restart and enable chrony
```bash
sudo systemctl restart chrony && sudo systemctl enable chrony
```

## Step 6 - Login banner
```bash
echo 'Authorised access to Northstar Engineering Ltd systems only. All activity is logged and monitored.' | sudo tee /etc/issue.net > /dev/null
sudo chmod 0644 /etc/issue.net
```

## Step 7 - SSH hardening
```bash
sudo tee /etc/ssh/sshd_config.d/10-nel-hardening.conf > /dev/null <<'EOF'
# Ansible managed
# NEL SSH hardening (requirement S1). Values: roles/linux_baseline/defaults/main.yml
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
X11Forwarding no
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2
Banner /etc/issue.net
EOF
sudo chmod 0644 /etc/ssh/sshd_config.d/10-nel-hardening.conf
```

## Step 8 - Check the SSH config, then reload (never reload an untested config)
```bash
sudo sshd -t && sudo systemctl reload ssh && echo SSH-OK
```
Expected: `SSH-OK`.

## Step 9 - Firewall: allow SSH FIRST, then enable with default deny
```bash
sudo ufw allow 22/tcp comment 'NEL management SSH'
sudo ufw default deny incoming
sudo ufw --force enable
```

## Step 10 - Web root with restricted permissions
```bash
sudo mkdir -p /var/www/nel
sudo chown root:www-data /var/www/nel && sudo chmod 0750 /var/www/nel
```

## Step 11 - Identification page (host-specific values, check them carefully)
```bash
sudo tee /var/www/nel/index.html > /dev/null <<'EOF'
<!DOCTYPE html>
<!-- Ansible managed -->
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>srv-acq-01 - Northstar Engineering Ltd</title>
</head>
<body>
  <h1>Northstar Engineering Ltd</h1>
  <table>
    <tr><th>Host</th><td>srv-acq-01</td></tr>
    <tr><th>Site</th><td>Acquired site (ACQ)</td></tr>
    <tr><th>Role</th><td>general server (acquired site)</td></tr>
    <tr><th>Address</th><td>192.168.56.22</td></tr>
  </table>
  <p>This page is managed by Ansible. Manual edits will be overwritten on the next run.</p>
</body>
</html>
EOF
sudo chown root:www-data /var/www/nel/index.html && sudo chmod 0640 /var/www/nel/index.html
```

## Step 12 - nginx site configuration
```bash
sudo tee /etc/nginx/sites-available/nel.conf > /dev/null <<'EOF'
# Ansible managed
server {
    listen 80 default_server;
    server_name srv-acq-01;

    root /var/www/nel;
    index index.html;

    server_tokens off;                       # hide the nginx version
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;

    location / {
        try_files $uri $uri/ =404;
    }
}
EOF
sudo chmod 0644 /etc/nginx/sites-available/nel.conf
```

## Step 13 - Enable the site, remove the default, test, reload
```bash
sudo ln -sf /etc/nginx/sites-available/nel.conf /etc/nginx/sites-enabled/nel.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx && echo NGINX-OK
```
Expected: `syntax is ok`, `test is successful`, `NGINX-OK`.

## Step 14 - Open HTTP and make nginx start at boot
```bash
sudo ufw allow 80/tcp comment 'NEL internal web service'
sudo systemctl enable --now nginx
```

## Step 15 - Verify (what an admin would check by hand)
```bash
systemctl is-active nginx chrony; systemctl is-enabled nginx
curl -s http://127.0.0.1/ | grep -E 'Host|Site'
sudo sshd -T | grep -E '^(permitrootlogin|passwordauthentication) '
sudo ufw status | grep ALLOW
```
Expected: `active` ×2, `enabled`, the srv-acq-01 / Acquired site lines, `permitrootlogin no`, `passwordauthentication no`, rules for 22 and 80 only.

**Stop the stopwatch.** Type `exit` to leave the VM.

---

## Timing sheet - fill in straight after finishing

| Item | Value |
|---|---|
| Date / start time | |
| End time | |
| **Elapsed (mm:ss)** | |
| Steps completed (out of 15) | |
| Commands you had to re-run or correct (list each + why) | |
| Anything you had to look up | |
| Did Step 15 show every expected value first time? (Y/N, what was wrong) | |
| How confident are you that srv-acq-01 now matches srv-main-01 exactly? (1–5) | |
| Notes (what was tedious, what could go wrong at 20 servers) | |

After this, Claude runs the **consistency check** (not timed as manual effort): `ansible-playbook playbooks/linux_servers.yml --check --diff --limit srv-acq-01` plus SHA-256 comparison of the five managed files against the Ansible-built reference (hashes in `evidence/logs/…_28_AN-06_reference_hashes.txt`). Every reported difference counts as a manual configuration error.
