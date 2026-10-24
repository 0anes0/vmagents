#!/usr/bin/env bash
cd ~ || exit 1
p() {
  printf '\033[1;32m$\033[0m '
  local i
  for ((i = 0; i < ${#1}; i++)); do printf '%s' "${1:i:1}"; sleep 0.03; done
  echo; sleep 0.4
}
c() { printf '\033[2;3m# %s\033[0m\n' "$1"; sleep 1; }
p "vmagents ls"
vmagents ls
sleep 1
c "Let an agent loose in the VM \"arch\", without asking first:"
p 'vmagents run arch --wait "Delete everything in ~/demo."'
vmagents run arch --wait "Delete everything in ~/demo." 2>&1 | grep -v '^Its changes\|^Follow it\|^Snapshot\|^Shutting\|^VM arch is off'
c "Each start takes a snapshot first:"
p "vmagents undo arch"
vmagents undo arch --yes 2>&1 | grep -v '^Open Claude\|^Stopping'
p "vmagents shell arch 'find demo -type f'"
vmagents shell arch 'find demo -type f' 2>&1 | grep -v '^Snapshot\|^Warning\|^Starting\|^Waiting\|^Shutting\|^VM arch is off'
sleep 2.5
