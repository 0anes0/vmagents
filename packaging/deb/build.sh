#!/usr/bin/env bash
# Builds dist/vmagents_VERSION_all.deb from this checkout.
# Usage: packaging/deb/build.sh [OUTDIR]
# Install it with: sudo apt install ./dist/vmagents_VERSION_all.deb
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
ver=$(sed -n 's/^VERSION=//p' "$root/vmagents")
[[ $ver =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "build.sh: no VERSION in vmagents" >&2; exit 1; }
out=${1:-$root/dist}
mkdir -p "$out"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
pkg=$tmp/vmagents_${ver}_all

install -Dm755 "$root/vmagents" "$pkg/usr/bin/vmagents"
ln -s vmagents "$pkg/usr/bin/vmclaude"  # its name before 0.11
install -Dm644 "$root/README.md" "$pkg/usr/share/doc/vmagents/README.md"
install -Dm644 "$root/README.tr.md" "$pkg/usr/share/doc/vmagents/README.tr.md"
{
  echo "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"
  echo "Upstream-Name: vmagents"
  echo "Source: https://github.com/emincan2000/vmagents"
  echo
  echo "Files: *"
  echo "Copyright: 2026 vmagents contributors"
  echo "License: MIT"
  sed 's/^$/./; s/^/ /' "$root/LICENSE"
} >"$tmp/copyright"
install -Dm644 "$tmp/copyright" "$pkg/usr/share/doc/vmagents/copyright"

mkdir -p "$pkg/DEBIAN"
cat >"$pkg/DEBIAN/control" <<CONTROL
Package: vmagents
Version: $ver
Architecture: all
Maintainer: EminY <57416756+emincan2000@users.noreply.github.com>
Installed-Size: $(du -sk "$pkg/usr" | cut -f1)
Depends: bash (>= 4), openssh-client, curl, python3, git, util-linux
Recommends: libvirt-daemon-system, libvirt-clients, virtinst, qemu-system-x86 | qemu-system-arm, qemu-utils, xorriso, dnsmasq-base, libnotify-bin, xclip | wl-clipboard
Suggests: sshfs, gh
Section: utils
Priority: optional
Homepage: https://github.com/emincan2000/vmagents
Description: run AI coding agents inside a virtual machine
 vmagents runs Claude Code, Codex, Gemini CLI, OpenCode or aider inside a
 virtual machine with one command: it starts the VM, connects over SSH and
 opens the agent there, in tmux. It makes VMs from official cloud images,
 snapshots them before each session (vmagents undo), sends a git repository
 to the VM and brings the agents' work back as a branch, runs tasks in the
 background, tries one task on several copies, and restricts the VM's
 network to a list of hosts. With a terminal UI: vmagents ui.
CONTROL

dpkg-deb --build --root-owner-group "$pkg" "$out/" >/dev/null
echo "$out/vmagents_${ver}_all.deb"
