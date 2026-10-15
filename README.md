# vmclaude

Open **Claude Code inside a virtual machine** with one command. It starts the
VM if needed, connects over SSH and runs Claude in tmux there. Claude then works
on the VM's files, not your computer's.

```
$ vmclaude
Starting VM dev...
Waiting for dev to get an IP address...
Waiting for SSH on 192.168.122.48:22...
 ╭──────────────────────────────────────╮
 │ ✻ Welcome to Claude Code!            │     ← running on the VM, in tmux
```

You can also skip the command. After setup, **any SSH login to the VM opens
Claude Code directly**: a terminal, a phone SSH app, PuTTY, Termius. There is
also an app-menu launcher.

> Türkçe açıklama aşağıda — [Türkçe](#türkçe).

## Features

- **One command:** `vmclaude` (or `vmclaude NAME`) connects and opens Claude.
- **libvirt VMs start themselves:** a stopped, paused or suspended domain is
  started. Its IP is read from libvirt (DHCP lease, guest agent or ARP).
  vmclaude then waits until sshd answers, not just until the port is open.
- **Sessions survive disconnects:** Claude runs in tmux on the VM. Close the
  window, lose Wi-Fi, connect again: you get the same session back.
- **One-step setup:** `vmclaude setup NAME` creates an SSH key and installs it
  on the VM (you type the VM password once). It installs tmux with the VM's
  package manager and Claude Code with the official installer.
- **Autostart on SSH login:** a small hook in `~/.bashrc` / `~/.zshrc` on the
  VM opens Claude on interactive SSH logins. Quit Claude (or press `Ctrl-b d`)
  to get a normal shell.
- **App-menu launcher:** `vmclaude desktop NAME`.
- **`vmclaude doctor`** checks each step: VM state, IP, sshd, key login,
  Claude, tmux, autostart.
- Several VMs, one default. Plain-text profiles. A single Bash script with no
  dependencies beyond OpenSSH.

## Requirements

- **Your computer:** Linux, bash 4+, OpenSSH client (`ssh`, `ssh-keygen`).
  `virsh` only if you use libvirt VMs.
- **The VM:** Linux with an SSH server (`openssh-server`), `curl`, and a user
  that can log in with a password once (or already has your key). `sudo` is
  needed only to install tmux.

Any VM works: libvirt/virt-manager/GNOME Boxes (qemu), VirtualBox, VMware,
Proxmox, a cloud server. Only libvirt VMs are started automatically. Start
other VMs yourself and give vmclaude their address.

## Install

```sh
git clone https://github.com/emincan2000/vmclaude
cd vmclaude
./install.sh                # puts vmclaude in ~/.local/bin
```

or without cloning:

```sh
curl -fsSL https://raw.githubusercontent.com/emincan2000/vmclaude/main/install.sh | bash
```

Uninstall with `./install.sh --uninstall`.

## Quick start

Run `vmclaude` with no arguments. The first time, it asks for the VM's details
and offers to set it up. Or do it by hand:

```sh
# a libvirt VM: started on demand, IP found automatically
vmclaude add dev --domain debian13 --user dev

# any other VM: give its address (and port, if forwarded)
vmclaude add dev --host 192.168.1.50 --user dev
vmclaude add vbox --host 127.0.0.1 --port 2222 --user dev   # VirtualBox NAT forward

vmclaude setup dev          # key, tmux, Claude Code, autostart
vmclaude                    # open Claude Code on the VM
```

The first time Claude runs on the VM, log in with `/login`. It prints a link to
open in your browser.

### Ways in

| From | How |
|---|---|
| Terminal | `vmclaude` (default VM) or `vmclaude dev` |
| App menu | `vmclaude desktop dev` adds **Claude Code (dev)** |
| Any SSH client | `ssh dev@VM` opens Claude (autostart) |
| A shell, not Claude | `vmclaude shell dev`, or quit Claude / `Ctrl-b d` |

Skip autostart for one login with `ssh -o SetEnv=LC_VMCLAUDE=off dev@VM`. This
works with the default `AcceptEnv LANG LC_*` of Debian and Ubuntu. Turn
autostart off with `vmclaude autostart dev off`.

To reach the VM from **another device** (your phone, for example): a libvirt NAT
network (`192.168.122.x`) is reachable only from the host. Use a bridged
network, a port forward on the host, or a VPN such as Tailscale on the VM.

## Commands

```
vmclaude                         connect to the default VM (asks to add one if none)
vmclaude NAME [CLAUDE_ARGS...]   connect to VM NAME, e.g. vmclaude dev --continue
vmclaude add NAME [options]      add a VM, or change fields of an existing one
    --host HOST  --user USER  --port PORT  --key FILE
    --domain LIBVIRT_DOMAIN  --uri LIBVIRT_URI  --dir DIR_ON_VM
    --session TMUX_SESSION  --no-tmux
vmclaude setup NAME [--no-install] [--no-autostart]
vmclaude connect [--hold] [--no-tmux] [NAME] [-- CLAUDE_ARGS...]
vmclaude shell NAME [CMD...]     plain shell or command on the VM
vmclaude autostart NAME on|off
vmclaude doctor NAME
vmclaude list | default NAME | desktop NAME | edit NAME | forget NAME | rm NAME
```

Claude arguments apply when a new tmux session starts. An existing session is
reattached as it is.

## Configuration

Profiles live in `~/.config/vmclaude/hosts/NAME.conf`. They are plain
`KEY=VALUE` files and are parsed, never executed:

```
HOST=192.168.122.48     # optional with DOMAIN
USER=dev
PORT=22
IDENTITY=~/.ssh/vmclaude_ed25519
DOMAIN=debian13         # libvirt domain
LIBVIRT_URI=qemu:///system
DIR=~/work              # where Claude starts on the VM (created if missing)
SESSION=claude          # tmux session; empty = no tmux
```

Environment: `VMCLAUDE_CONFIG_DIR` (another config folder),
`VMCLAUDE_BOOT_TIMEOUT` (seconds to wait for the VM, default 180).

## How it works

- `ssh -l USER -p PORT -i KEY -o HostKeyAlias=vmclaude-NAME`. The host key is
  stored under the profile name in vmclaude's own `known_hosts`, so a VM whose
  DHCP address changes keeps its identity. The first connection accepts the key
  (`StrictHostKeyChecking=accept-new`). After that, a changed key is refused
  until you run `vmclaude forget NAME`, for example after reinstalling the VM.
- On the VM a short POSIX `sh` script runs. It adds `~/.local/bin` to `PATH`,
  goes to `DIR` and runs `tmux new-session -A -s claude claude ...`. Arguments
  are quoted for `sh`, so the VM user's login shell (bash, zsh, fish) does not
  matter.
- Booting libvirt VMs: `virsh start`, then `virsh domifaddr`, then wait for the
  `SSH-2.0` banner. NAT forwards (passt, slirp, VirtualBox) accept connections
  before sshd is up, so an open port alone is not enough.
- vmclaude does not change the VM's sshd settings. Once key login works, you
  may want to turn off password login (`PasswordAuthentication no`).

## Tests

```sh
python3 -m unittest discover -s tests -t .
```

- `tests/test_cli.py` runs vmclaude against a fake `ssh` and `virsh`. The
  scripts meant for the VM really run, under `sh`, in a throwaway home
  directory. The autostart hook is tested in real interactive bash and zsh on
  a pseudo-terminal.
- `tests/test_e2e.py` uses the real OpenSSH client against a local SSH server
  (needs `asyncssh`, skipped otherwise). It covers password then key login,
  host-key pinning and quoting through a real remote shell.
- By hand, on a Debian 13 cloud image in qemu: setup (key, `apt-get install
  tmux`, the Claude Code installer), connect, detach and reattach, autostart on
  a plain `ssh` login, and skipping it with `LC_VMCLAUDE=off`.

## Limitations

- Linux VMs only. A Windows VM has no `sh`/tmux; for Windows, SSH in and run
  `claude` yourself.
- Tested on Linux hosts. macOS needs bash 4+ (Homebrew) and `timeout`
  (coreutils).
- Only libvirt VMs are started automatically.

## License

MIT

---

## Türkçe

**vmclaude**, Claude Code'u tek komutla bir **sanal makinenin içinde** açar.
Gerekirse VM'i başlatır, SSH ile bağlanır ve Claude'u orada tmux içinde
çalıştırır. Claude böylece senin bilgisayarının değil, VM'in dosyaları üzerinde
çalışır.

**Kurulum ve ilk kullanım:**

```sh
git clone https://github.com/emincan2000/vmclaude && cd vmclaude && ./install.sh

vmclaude add dev --domain debian13 --user dev   # libvirt VM'i (otomatik başlar, IP'si bulunur)
# ya da: vmclaude add dev --host 192.168.1.50 --user dev
vmclaude setup dev    # SSH anahtarı + tmux + Claude Code + otomatik başlatma (VM şifresi bir kez sorulur)
vmclaude              # Claude Code'u VM'de aç
```

Argümansız `vmclaude` ilk seferde VM bilgilerini sorar ve kurulumu teklif eder.
Claude VM'de ilk kez açıldığında `/login` ile giriş yap.

**Nasıl açılır:**

- **Terminal:** `vmclaude` ya da `vmclaude dev`
- **Uygulama menüsü:** `vmclaude desktop dev` komutu "Claude Code (dev)" kısayolunu ekler.
- **Herhangi bir SSH uygulaması** (telefon, Termius, PuTTY): VM'e SSH ile
  bağlanınca Claude doğrudan açılır. Claude'dan çıkınca ya da `Ctrl-b d` ile
  normal kabuğa düşersin. Bir seferlik atlamak için:
  `ssh -o SetEnv=LC_VMCLAUDE=off ...`. Kapatmak için:
  `vmclaude autostart dev off`.
- Bağlantı koparsa Claude tmux içinde çalışmaya devam eder. Tekrar
  bağlandığında aynı oturuma dönersin.

**Sorun mu var?** `vmclaude doctor dev` her adımı (VM durumu, IP, sshd, anahtar
girişi, Claude, tmux) tek tek kontrol eder.

**Notlar:** VM Linux olmalı (Windows VM desteklenmez). Otomatik başlatma
yalnızca libvirt VM'lerinde çalışır. VirtualBox gibi diğer VM'leri kendin
başlatıp `--host`/`--port` ver. Telefondan erişmek için VM'in ağdan
erişilebilir olması gerekir (köprü ağ, port yönlendirme ya da Tailscale).

---

If vmclaude saved you some setup time, a ⭐ on GitHub helps others find it.
