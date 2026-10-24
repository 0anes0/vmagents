#!/usr/bin/env bash
# The README's demo: an agent deletes a project in the VM, undo brings it back.
cd ~ || exit 1
p() {
  printf '\033[1;32m$\033[0m '
  local i
  for ((i = 0; i < ${#1}; i++)); do printf '%s' "${1:i:1}"; sleep 0.035; done
  echo; sleep 0.5
}
c() { printf '\033[2;3m# %s\033[0m\n' "$1"; sleep 1.2; }
c "A project in the VM \"arch\":"
p "vmagents shell arch 'find demo -type f'"
vmagents shell arch 'find demo -type f'
sleep 1.5
c "Let an agent loose on it, without asking first:"
p 'vmagents run arch --wait "Delete everything in ~/demo."'
vmagents run arch --wait "Delete everything in ~/demo." 2>&1 | grep -v '^Its changes\|^Follow it'
p "vmagents shell arch 'ls -A demo'"
vmagents shell arch 'ls -A demo; echo "(empty)"'
sleep 1.5
c "It is a VM, and each start took a snapshot:"
p "vmagents undo arch"
vmagents undo arch --yes 2>&1 | grep -v '^Open Claude'
p "vmagents shell arch 'find demo -type f'"
vmagents shell arch 'find demo -type f' 2>&1 | grep -v '^Snapshot\|^Warning'
sleep 3
