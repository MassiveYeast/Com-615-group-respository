#!/usr/bin/env bash
# Builds the Ansible control node on WSL Ubuntu 24.04 (docs/DECISIONS.md D-01).
# Safe to re-run: every step checks before it changes anything.
#
#   Windows:  wsl --install -d Ubuntu-24.04
#   WSL:      bash "control-node/setup_control_node.sh"     (run from the ansible/ folder)
#
# Secrets are created locally and NEVER written into the repo (it is public):
#   ~/.ssh/nel_ansible_ed25519      private key used to manage the servers
#   ~/.ansible/nel_vault_pass       ansible-vault password
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$HOME/.venvs/ansible"
KEY="$HOME/.ssh/nel_ansible_ed25519"
VAULT_PASS="$HOME/.ansible/nel_vault_pass"
step() { printf '\n==> %s\n' "$*"; }

step "1/7 OS packages"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv python3-pip git sshpass openssh-client >/dev/null
lsb_release -ds

step "2/7 WSL mount options (metadata, so Ansible trusts ansible.cfg)"
if ! cmp -s "$PROJECT_DIR/control-node/wsl.conf" /etc/wsl.conf; then
  sudo cp "$PROJECT_DIR/control-node/wsl.conf" /etc/wsl.conf
  echo "Updated /etc/wsl.conf - run 'wsl --shutdown' in Windows, then reopen WSL."
else
  echo "/etc/wsl.conf already correct"
fi

step "3/7 Python venv with pinned tools (requirements-dev.txt)"
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$PROJECT_DIR/requirements-dev.txt"
grep -q 'venvs/ansible/bin/activate' "$HOME/.bashrc" || echo "source $VENV/bin/activate" >> "$HOME/.bashrc"
"$VENV/bin/ansible" --version | head -1

step "4/7 Pinned Ansible collections (requirements.yml) on the Linux filesystem (D-04)"
"$VENV/bin/ansible-galaxy" collection install -r "$PROJECT_DIR/requirements.yml" -p "$HOME/.ansible/collections" \
  | grep -E 'installed|already' || true

step "5/7 SSH key for managing servers"
mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
if [ ! -f "$KEY" ]; then
  ssh-keygen -t ed25519 -N '' -C 'nel-ansible-control' -f "$KEY" -q
  echo "Created $KEY"
else
  echo "$KEY already exists"
fi
cp "$KEY.pub" "$PROJECT_DIR/lab/control_node.pub"   # public half only, used by lab/Vagrantfile

step "6/7 Vault password file"
mkdir -p "$HOME/.ansible" && chmod 700 "$HOME/.ansible"
if [ -f "$VAULT_PASS" ]; then
  chmod 600 "$VAULT_PASS"; echo "$VAULT_PASS present (mode 600)"
else
  echo "MISSING: $VAULT_PASS"
  echo "Get the vault password from the project owner, then:"
  echo "  install -m 600 /dev/null $VAULT_PASS && nano $VAULT_PASS"
fi

step "7/7 Check: does Ansible load the project config?"
cd "$PROJECT_DIR"
"$VENV/bin/ansible" --version | grep 'config file'
stat -c 'project folder permissions: %a' "$PROJECT_DIR"
