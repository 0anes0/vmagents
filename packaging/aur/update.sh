#!/usr/bin/env bash
# Sets the AUR package to a released version: pkgver, pkgrel=1, the
# checksum of GitHub's tarball of tag vVERSION, and .SRCINFO.
# Usage: packaging/aur/update.sh [VERSION]   (default: the VERSION in vmagents)
# Then, in a clone of ssh://aur@aur.archlinux.org/vmagents.git: copy
# PKGBUILD and .SRCINFO there, commit and push.
set -euo pipefail

dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ver=${1:-$(sed -n 's/^VERSION=//p' "$dir/../../vmagents")}
[[ $ver =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "update.sh: not a version: $ver" >&2; exit 2; }
url=https://github.com/emincan2000/vmagents/archive/refs/tags/v$ver.tar.gz
sum=$(curl -fsSL "$url" | sha256sum | cut -d' ' -f1) || { echo "update.sh: cannot fetch $url" >&2; exit 1; }
sed -i "s/^pkgver=.*/pkgver=$ver/; s/^pkgrel=.*/pkgrel=1/; s/^sha256sums=.*/sha256sums=('$sum')/" "$dir/PKGBUILD"

# .SRCINFO, as makepkg --printsrcinfo writes it for this PKGBUILD.
# shellcheck disable=SC2154 # pkgname and the rest come from the PKGBUILD
(
  # shellcheck disable=SC1091
  source "$dir/PKGBUILD"
  {
    echo "pkgbase = $pkgname"
    printf '\tpkgdesc = %s\n\tpkgver = %s\n\tpkgrel = %s\n\turl = %s\n' "$pkgdesc" "$pkgver" "$pkgrel" "$url"
    for a in "${arch[@]}"; do printf '\tarch = %s\n' "$a"; done
    for l in "${license[@]}"; do printf '\tlicense = %s\n' "$l"; done
    for d in "${depends[@]}"; do printf '\tdepends = %s\n' "$d"; done
    for d in "${optdepends[@]}"; do printf '\toptdepends = %s\n' "$d"; done
    for s in "${source[@]}"; do printf '\tsource = %s\n' "$s"; done
    for s in "${sha256sums[@]}"; do printf '\tsha256sums = %s\n' "$s"; done
    echo
    echo "pkgname = $pkgname"
  } >"$dir/.SRCINFO"
)
echo "PKGBUILD and .SRCINFO are at $ver ($sum)."
