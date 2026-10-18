# Packages

- `deb/build.sh [OUTDIR]` builds `vmagents_VERSION_all.deb` from this checkout
  (`dpkg-deb`). CI builds and installs it on every push; on every `v*` tag the
  release workflow attaches it to the GitHub release.
- `aur/PKGBUILD` and `aur/.SRCINFO` are the Arch Linux (AUR) package. After a
  tag is pushed, `aur/update.sh` sets them to that version (the checksum of
  GitHub's tarball of the tag); then copy both into a clone of
  `ssh://aur@aur.archlinux.org/vmagents.git`, commit and push (needs an AUR
  account with an SSH key). To try it locally: `cd aur && makepkg -si`.

A release: set `VERSION=` in `vmagents`, commit, tag `vX.Y.Z`, push both;
then `packaging/aur/update.sh` and publish to the AUR.
