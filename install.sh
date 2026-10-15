#!/usr/bin/env bash
# Install vmclaude for the current user.
# Usage: ./install.sh [--prefix DIR] [--uninstall]
#    or: curl -fsSL https://raw.githubusercontent.com/emincan2000/vmclaude/main/install.sh | bash
set -euo pipefail

RAW=https://raw.githubusercontent.com/emincan2000/vmclaude/main/vmclaude
PREFIX=$HOME/.local
UNINSTALL=0
while (($#)); do
  case $1 in
    --prefix) PREFIX=${2:?--prefix needs a directory}; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h | --help) sed -n '2,4p' "$0"; exit 0 ;;
    *) echo "install.sh: unknown option $1" >&2; exit 2 ;;
  esac
done
BIN=$PREFIX/bin/vmclaude

if ((UNINSTALL)); then
  rm -f "$BIN"
  echo "Removed $BIN."
  echo "Your VM profiles stay in ${XDG_CONFIG_HOME:-$HOME/.config}/vmclaude; delete that folder to remove them."
  exit 0
fi

mkdir -p "$PREFIX/bin"
SRC=
if [[ -n ${BASH_SOURCE[0]:-} ]]; then SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd) || SRC=; fi
if [[ -n $SRC && -f $SRC/vmclaude ]]; then
  cp "$SRC/vmclaude" "$BIN.tmp"
else
  command -v curl >/dev/null || { echo "install.sh: curl is required" >&2; exit 1; }
  curl -fsSL "$RAW" -o "$BIN.tmp"
fi
chmod 755 "$BIN.tmp"
mv -f "$BIN.tmp" "$BIN"
echo "Installed $BIN ($("$BIN" --version))"

for tool in ssh ssh-keygen; do
  command -v "$tool" >/dev/null || echo "note: $tool is missing — install openssh-client" >&2
done
case ":$PATH:" in
  *":$PREFIX/bin:"*) ;;
  *) echo "note: $PREFIX/bin is not on your PATH; add it, e.g. in ~/.bashrc or ~/.zshrc:"
     echo "  export PATH=\"$PREFIX/bin:\$PATH\"" ;;
esac
echo "Next: vmclaude   (it asks for your VM the first time)"
