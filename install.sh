#!/usr/bin/env bash
# Install vmforai for the current user.
# Usage: ./install.sh [--prefix DIR] [--no-deps] [--no-modify-path] [--uninstall]
#    or: curl -fsSL https://raw.githubusercontent.com/emincan2000/vmforai/main/install.sh | bash
# Then what vmforai uses (libvirt, QEMU, ...) with the package manager; --no-deps: not that.
set -euo pipefail

RAW=https://raw.githubusercontent.com/emincan2000/vmforai/main/vmforai
PREFIX=$HOME/.local
UNINSTALL=0
MODIFY_PATH=1
DEPS=1
[[ -n ${VMFORAI_NO_DEPS:-} ]] && DEPS=0
while (($#)); do
  case $1 in
    --prefix) PREFIX=${2:?--prefix needs a directory}; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    --deps) DEPS=1; shift ;;  # (the default now)
    --no-deps) DEPS=0; shift ;;
    --no-modify-path) MODIFY_PATH=0; shift ;;
    -h | --help) sed -n '2,5p' "$0"; exit 0 ;;
    *) echo "install.sh: unknown option $1" >&2; exit 2 ;;
  esac
done
BIN=$PREFIX/bin/vmforai

if ((UNINSTALL)); then
  rm -f "$BIN"
  [[ -L $PREFIX/bin/vmf ]] && rm -f "$PREFIX/bin/vmf"
  for old in vmagents vmclaude; do [[ -L $PREFIX/bin/$old ]] && rm -f "$PREFIX/bin/$old"; done
  for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do  # the PATH line install.sh added
    [[ -f $rc ]] && grep -qF '  # vmforai' "$rc" && sed -i '/  # vmforai$/d' "$rc"
  done
  echo "Removed $BIN."
  echo "Your VM profiles stay in ${XDG_CONFIG_HOME:-$HOME/.config}/vmforai; delete that folder to remove them."
  exit 0
fi

mkdir -p "$PREFIX/bin"
SRC=
if [[ -n ${BASH_SOURCE[0]:-} ]]; then SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd) || SRC=; fi
if [[ -n $SRC && -f $SRC/vmforai ]]; then
  cp "$SRC/vmforai" "$BIN.tmp"
else
  command -v curl >/dev/null || { echo "install.sh: curl is required" >&2; exit 1; }
  curl -fsSL "$RAW" -o "$BIN.tmp"
fi
chmod 755 "$BIN.tmp"
mv -f "$BIN.tmp" "$BIN"
echo "Installed $BIN ($("$BIN" --version))"
# vmf: short for it.
ln -sfn vmforai "$PREFIX/bin/vmf"
# Its old names (vmagents until 0.24, vmclaude until 0.10) keep working.
for old in vmagents vmclaude; do
  OLD=$PREFIX/bin/$old
  if [[ -e $OLD || -L $OLD ]]; then
    ln -sfn vmforai "$OLD"
    echo "$old is now called vmforai (short: vmf); \"$old\" still works. Settings move to the new name on first use."
  fi
done

for tool in ssh ssh-keygen; do
  command -v "$tool" >/dev/null || echo "note: $tool is missing — install openssh-client" >&2
done
# Not on the PATH yet: added for the shells to come (as uv and rustup do).
case ":$PATH:" in
  *":$PREFIX/bin:"*) ;;
  *)
    line="export PATH=\"$PREFIX/bin:\$PATH\"  # vmforai"
    added=''
    if ((MODIFY_PATH)); then
      for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
        [[ -f $rc || $rc == "$HOME/.bashrc" ]] || continue
        grep -qsF "$PREFIX/bin" "$rc" || { printf '\n%s\n' "$line" >>"$rc" && added+=" ${rc/#"$HOME"/\~}"; }
      done
    fi
    if [[ -n $added ]]; then
      echo "$PREFIX/bin is now on the PATH in$added: open a new terminal (or: $line)"
    else
      echo "note: $PREFIX/bin is not on your PATH; add it, e.g. in ~/.bashrc or ~/.zshrc:"
      echo "  $line"
    fi ;;
esac
if ((DEPS)) && [[ $(uname -s) == Linux ]]; then
  # What vmforai uses, at once (sudo asks on the terminal, also when this
  # script comes through a pipe). Done: no question again on the first run.
  echo ""
  if "$BIN" deps --yes; then
    mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/vmforai" && : >"${XDG_CONFIG_HOME:-$HOME/.config}/vmforai/deps-checked"
  else
    echo "note: some of what vmforai uses is missing; later: vmforai deps" >&2
  fi
elif ! "$BIN" deps --check >/dev/null 2>&1; then
  echo "Some of what vmforai uses is missing here; vmforai installs it on its first run (or now: vmforai deps)"
fi
echo "Next: vmforai   (it asks for your VM the first time)"
