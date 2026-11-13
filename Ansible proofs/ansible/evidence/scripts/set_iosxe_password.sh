#!/usr/bin/env bash
# Asks for the DevNet sandbox device password (not echoed) and stores it in ~/.iosxe_env (mode 600).
# The password never appears on screen, in shell history, or in this repo.
set -eu
f=~/.iosxe_env
[ -f "$f" ] || { echo "$f missing"; exit 1; }
read -rsp "Sandbox password (paste, then Enter): " p; echo
[ -n "$p" ] || { echo "empty - nothing saved"; exit 1; }
tmp=$(mktemp); chmod 600 "$tmp"
grep -v '^export IOSXE_PASS=' "$f" > "$tmp"
printf 'export IOSXE_PASS=%q\n' "$p" >> "$tmp"
unset p
mv "$tmp" "$f"; chmod 600 "$f"
echo "saved to $f (mode $(stat -c %a "$f"))"
