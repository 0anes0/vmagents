#!/usr/bin/env bash
# Install vmagents for the current user.
# Usage: ./install.sh [--prefix DIR] [--deps] [--uninstall]
#    or: curl -fsSL https://raw.githubusercontent.com/emincan2000/vmagents/main/install.sh | bash [-s -- --deps]
# --deps: then also what vmagents uses (libvirt, QEMU, ...), with the package manager.
set -euo pipefail

RAW=https://raw.githubusercontent.com/emincan2000/vmagents/main/vmagents
PREFIX=$HOME/.local
UNINSTALL=0
DEPS=0
while (($#)); do
  case $1 in
    --prefix) PREFIX=${2:?--prefix needs a directory}; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    --deps) DEPS=1; shift ;;
    -h | --help) sed -n '2,5p' "$0"; exit 0 ;;
    *) echo "install.sh: unknown option $1" >&2; exit 2 ;;
  esac
done
BIN=$PREFIX/bin/vmagents

if ((UNINSTALL)); then
  rm -f "$BIN"
  [[ -L $PREFIX/bin/vmclaude ]] && rm -f "$PREFIX/bin/vmclaude"
  echo "Removed $BIN."
  echo "Your VM profiles stay in ${XDG_CONFIG_HOME:-$HOME/.config}/vmagents; delete that folder to remove them."
  exit 0
fi

mkdir -p "$PREFIX/bin"
SRC=
if [[ -n ${BASH_SOURCE[0]:-} ]]; then SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd) || SRC=; fi
if [[ -n $SRC && -f $SRC/vmagents ]]; then
  cp "$SRC/vmagents" "$BIN.tmp"
else
  command -v curl >/dev/null || { echo "install.sh: curl is required" >&2; exit 1; }
  curl -fsSL "$RAW" -o "$BIN.tmp"
fi
chmod 755 "$BIN.tmp"
mv -f "$BIN.tmp" "$BIN"
echo "Installed $BIN ($("$BIN" --version))"
# Before 0.11 this was "vmclaude": that name keeps working.
OLD=$PREFIX/bin/vmclaude
if [[ -e $OLD || -L $OLD ]]; then
  ln -sfn vmagents "$OLD"
  echo "vmclaude was renamed to vmagents; \"vmclaude\" still works. Settings move to the new name on first use."
fi

for tool in ssh ssh-keygen; do
  command -v "$tool" >/dev/null || echo "note: $tool is missing — install openssh-client" >&2
done
case ":$PATH:" in
  *":$PREFIX/bin:"*) ;;
  *) echo "note: $PREFIX/bin is not on your PATH; add it, e.g. in ~/.bashrc or ~/.zshrc:"
     echo "  export PATH=\"$PREFIX/bin:\$PATH\"" ;;
esac
if ((DEPS)); then
  # (sudo asks on the terminal even when this script comes through a pipe.)
  "$BIN" deps --yes || echo "note: some of what vmagents uses is missing; see: vmagents deps --check" >&2
else
  "$BIN" deps --check >/dev/null 2>&1 || echo "Some of what vmagents uses is missing here; install it: vmagents deps"
fi
echo "Next: vmagents   (it asks for your VM the first time)"
