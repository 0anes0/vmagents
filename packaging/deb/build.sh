#!/usr/bin/env bash
# Builds dist/vmforai_VERSION_all.deb from this checkout.
# Usage: packaging/deb/build.sh [OUTDIR]
# Install it with: sudo apt install ./dist/vmforai_VERSION_all.deb
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
ver=$(sed -n 's/^VERSION=//p' "$root/vmforai")
[[ $ver =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "build.sh: no VERSION in vmforai" >&2; exit 1; }
out=${1:-$root/dist}
mkdir -p "$out"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
pkg=$tmp/vmforai_${ver}_all

install -Dm755 "$root/vmforai" "$pkg/usr/bin/vmforai"
ln -s vmforai "$pkg/usr/bin/vmf"  # short for it
ln -s vmforai "$pkg/usr/bin/vmagents"  # its names before: until 0.24,
ln -s vmforai "$pkg/usr/bin/vmclaude"  # and until 0.10
install -Dm644 "$root/README.md" "$pkg/usr/share/doc/vmforai/README.md"
install -Dm644 "$root/README.tr.md" "$pkg/usr/share/doc/vmforai/README.tr.md"
{
  echo "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"
  echo "Upstream-Name: vmforai"
  echo "Source: https://github.com/emincan2000/vmforai"
  echo
  echo "Files: *"
  echo "Copyright: 2026 vmforai contributors"
  echo "License: MIT"
  sed 's/^$/./; s/^/ /' "$root/LICENSE"
} >"$tmp/copyright"
install -Dm644 "$tmp/copyright" "$pkg/usr/share/doc/vmforai/copyright"

mkdir -p "$pkg/DEBIAN"
cat >"$pkg/DEBIAN/control" <<CONTROL
Package: vmforai
Provides: vmagents
Replaces: vmagents
Conflicts: vmagents
Version: $ver
Architecture: all
Maintainer: EminY <57416756+emincan2000@users.noreply.github.com>
Installed-Size: $(du -sk "$pkg/usr" | cut -f1)
Depends: bash (>= 4), openssh-client, curl, python3, git, util-linux
Recommends: libvirt-daemon-system, libvirt-clients, virtinst, qemu-system-x86 | qemu-system-arm, qemu-utils, xorriso, dnsmasq-base, libnotify-bin, xclip | wl-clipboard
Suggests: sshfs, gh
Section: utils
Priority: optional
Homepage: https://github.com/emincan2000/vmforai
Description: run AI coding agents inside a virtual machine
 vmforai runs Claude Code, Codex, Gemini CLI, OpenCode or aider inside a
 virtual machine with one command: it starts the VM, connects over SSH and
 opens the agent there, in tmux. It makes VMs from official cloud images,
 snapshots them before each session (vmforai undo), sends a git repository
 to the VM and brings the agents' work back as a branch, runs tasks in the
 background, tries one task on several copies, and restricts the VM's
 network to a list of hosts. With a terminal UI: vmforai ui.
CONTROL

dpkg-deb --build --root-owner-group "$pkg" "$out/" >/dev/null
echo "$out/vmforai_${ver}_all.deb"
