# vmclaude

Open **Claude Code inside a virtual machine** with one command. It starts the
VM if needed, connects over SSH and runs Claude there: in tmux on **Linux**
VMs, and also on **Windows** VMs. Claude then works on the VM's files, not
your computer's.

```
$ vmclaude
Starting VM dev...
Waiting for dev to get an IP address...
Waiting for SSH on 192.168.122.48:22...
 ╭──────────────────────────────────────╮
 │ ✻ Welcome to Claude Code!            │     ← running on the VM, in tmux
```

No VM yet? `vmclaude create dev` makes one: a fresh Debian VM with Claude
Code inside, usually in half a minute to two minutes once the image is
downloaded, without a single password prompt.

You can also skip the command. After setup, **any SSH login to the VM opens
Claude Code directly**: a terminal, a phone SSH app, PuTTY, Termius. There is
also an app-menu launcher.

> Türkçe açıklama aşağıda — [Türkçe](#türkçe).

## Features

- **One command:** `vmclaude` (or `vmclaude NAME`) connects and opens Claude.
- **New VMs on demand:** `vmclaude create NAME` builds a libvirt VM from an
  official cloud image (Debian 13, Debian 12, Ubuntu 24.04 or Arch Linux)
  and sets it up.
  `vmclaude delete NAME` removes it again, `vmclaude prune` the downloaded
  images. See [Create a VM](#create-a-vm).
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
- **Windows VMs too:** detected from the SSH banner. Setup installs Git for
  Windows and Claude Code there; see [Windows VMs](#windows-vms).
- Several VMs, one default. Plain-text profiles. A single Bash script with no
  dependencies beyond OpenSSH.

## Requirements

- **Your computer:** Linux, bash 4+, OpenSSH client (`ssh`, `ssh-keygen`).
  `virsh` only if you use libvirt VMs.
- **A Linux VM:** an SSH server (`openssh-server`), `curl`, and a user that
  can log in with a password once (or already has your key). `sudo` is needed
  only to install tmux.
- **A Windows VM:** Windows 10 1809+ or 11 with the OpenSSH Server feature on;
  see [Windows VMs](#windows-vms).

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

**Starting from nothing** (Linux with libvirt):

```sh
vmclaude create dev         # new Debian VM + Claude Code, no password needed
vmclaude dev                # open Claude Code in it
```

**With a VM you already have:** run `vmclaude` with no arguments. The first
time, it asks for the VM's details and offers to set it up. Or do it by hand:

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
vmclaude create NAME [options]   make a new Linux VM and set it up
    --image debian13|debian12|ubuntu24.04|arch  --memory MB  --cpus N  --disk GB
    --user USER  --uri LIBVIRT_URI  --no-setup
vmclaude delete NAME [--yes]     delete a VM made with create, and its disk
vmclaude prune                   remove downloaded images no VM uses any more
vmclaude add NAME [options]      add an existing VM, or change fields of a profile
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
OS=linux                # or windows; detected from the SSH banner on first use
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

## Create a VM

```sh
vmclaude create dev                                   # Debian 13, 4 GB RAM, 2 CPUs, 20 GB disk
vmclaude create big --memory 16384 --cpus 8 --disk 100
vmclaude create u --image ubuntu24.04
vmclaude create a --image arch
vmclaude delete dev                                   # asks you to type the name
vmclaude prune                                        # free the space of unused images
```

Needs `virsh` and `virt-install` (`sudo apt install libvirt-daemon-system
virtinst`, and your user in the `libvirt` group). What `create` does:

1. Downloads the official cloud image once into `~/.cache/vmclaude/images`
   and checks it against the distribution's published SHA-512/SHA-256 sums.
2. Copies it into the libvirt storage pool `default` as a shared base volume.
   Each VM gets a thin copy-on-write disk on top of it, so a new VM takes
   seconds and little space. While that base volume exists, later VMs need no
   download at all.
3. Starts the VM with a cloud-init seed on a small read-only disk.
   cloud-init creates your user with your vmclaude SSH key and password-less
   `sudo`, and installs tmux. The account has no password at all.
4. Waits until the VM accepts the key, then runs `vmclaude setup`: installs
   Claude Code and the SSH-login autostart.

`prune` removes base volumes that no VM disk is built on, and the download
cache in `~/.cache/vmclaude`.

The VM is on libvirt's `default` NAT network and shows up in virt-manager
like any other. Other pools or networks: `VMCLAUDE_POOL`, `VMCLAUDE_NETWORK`.

Arch's image comes from `geo.mirror.pkgbuild.com`, which can be slow from some
places. Pick another mirror with `VMCLAUDE_ARCH_MIRROR`, e.g.
`VMCLAUDE_ARCH_MIRROR=https://mirrors.dotsrc.org/archlinux vmclaude create a --image arch`.
The checksum still comes from Arch's own server.

Two details that real runs turned up: the seed is a virtio disk, not
virt-install's `--cloud-init` CD-ROM, because the Debian 12 cloud kernel has
no driver for that SATA CD-ROM. And the VM gets a video device even without a
screen, because without one the GRUB of the Debian cloud images resets the VM
in a loop.

`delete` only deletes VMs that `create` made. The profile has to say so, and
so does the VM's own libvirt description ("created by vmclaude"). Your other
VMs cannot be deleted with it.

## Windows VMs

Turn on the SSH server in Windows once, in an administrator PowerShell
(or Settings → Apps → Optional features → OpenSSH Server):

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd; Set-Service sshd -StartupType Automatic
```

Then it works as on Linux:

```sh
vmclaude add win10 --domain win10 --user emin   # or --host IP
vmclaude setup win10
vmclaude win10
```

What is different:

- **No tmux.** Closing the connection ends Claude's session; `claude
  --continue` picks the conversation up again.
- **setup** puts your key in `~\.ssh\authorized_keys`, and for administrators
  also in `C:\ProgramData\ssh\administrators_authorized_keys`, which is the
  only file Windows OpenSSH reads for them. It installs Git for Windows
  (Claude Code uses its Bash): it tries winget, which often fails over SSH
  ("Failed when searching source"), then the official installer from the
  git-for-windows GitHub releases. It
  installs Claude Code like `https://claude.ai/install.ps1` does: same
  download, same SHA-256 check, same `claude install`. The download uses
  `curl.exe`, because `Invoke-WebRequest` in Windows PowerShell 5.1 times out
  on the 270 MB binary.
- **Autostart** goes into your PowerShell profile. That needs Windows
  PowerShell as OpenSSH's default shell (the `DefaultShell` registry value),
  and an execution policy that runs profile scripts. If your user's policy is
  `Restricted`, setup sets it to `RemoteSigned` for your user and says so.
  `vmclaude shell NAME` opens PowerShell without starting Claude.
- Commands are sent as `powershell -EncodedCommand`. That works under both
  `cmd.exe` and PowerShell as the default shell and needs no quoting. Claude's
  arguments are passed through Windows' own command-line rules, so quotes,
  spaces and trailing backslashes arrive unchanged.
- Claude Code on Windows sometimes does not exit after you quit it under
  OpenSSH: it gives the console back but the process stays. vmclaude notices
  the console switching back to line mode and ends the leftover process, so
  the connection closes.

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
- `tests/test_create.py` runs `create` and `delete` against fake `curl`,
  `virsh` and `virt-install`, including that `delete` refuses VMs it did not
  create.
- `tests/test_windows.py` checks OS detection and decodes the PowerShell
  commands sent to Windows VMs.
- By hand, on a Debian 13 cloud image in qemu: setup (key, `apt-get install
  tmux`, the Claude Code installer), connect, detach and reattach, autostart on
  a plain `ssh` login, and skipping it with `LC_VMCLAUDE=off`.
- By hand, `vmclaude create` on libvirt 11.3 (`qemu:///system`) with all
  four images (Debian 13, Debian 12, Ubuntu 24.04, Arch Linux): download, checksum, base
  volume, VM, cloud-init, Claude Code, doctor, shut down and start again
  through `vmclaude NAME`, `delete` and `prune`. These runs found the two
  details described under [Create a VM](#create-a-vm).
- Inside that Arch Linux VM (kernel 7.2, `/bin/sh` is bash there): connect,
  detach and reattach the tmux session, autostart on a plain `ssh` login, and
  the whole test suite with shellcheck, asyncssh and zsh installed.
- By hand, on Windows 10 22H2 (libvirt, OpenSSH for Windows 9.5): setup (key
  as administrator, Git via the fallback installer since winget failed over
  SSH, Claude Code), doctor, connect and quit,
  autostart on a plain `ssh` login, `vmclaude shell`. Also 13 hard arguments
  (quotes, trailing backslash, empty, `%PATH%`, `&|<>^`, Turkish and curly
  quotes) checked byte for byte.

## Limitations

- Windows VMs have no tmux, so sessions end with the connection.
- Skipping autostart for one login with `LC_VMCLAUDE=off` works on Linux VMs
  only. Windows OpenSSH does not accept the variable; use `vmclaude shell`.
- Tested on Linux hosts. macOS needs bash 4+ (Homebrew) and `timeout`
  (coreutils).
- Only libvirt VMs are started automatically.

## License

MIT

---

## Türkçe

**vmclaude**, Claude Code'u tek komutla bir **sanal makinenin içinde** açar.
Gerekirse VM'i başlatır, SSH ile bağlanır ve Claude'u orada çalıştırır: Linux
VM'lerde tmux içinde, **Windows** VM'lerde de doğrudan. Claude böylece senin
bilgisayarının değil, VM'in dosyaları üzerinde çalışır.

**Hiç VM'in yoksa:**

```sh
vmclaude create dev   # resmi Debian bulut imajından yeni VM + Claude Code, şifresiz
vmclaude dev          # Claude Code'u içinde aç
```

İmaj (Debian 13, Debian 12, `--image ubuntu24.04` ya da `--image arch`) bir kez indirilip
doğrulanır. Sonraki VM'ler genelde yarım dakika ile iki dakika arasında hazır
olur. `vmclaude delete dev` VM'i diskiyle birlikte siler; yalnızca `create`
ile oluşturulmuş VM'lerde çalışır, diğer VM'lerine dokunamaz.
`vmclaude prune` artık kullanılmayan imajları silip yer açar.

**Var olan bir VM ile kurulum ve ilk kullanım:**

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

**Windows VM:** Windows'ta bir kez OpenSSH Sunucusu'nu aç (Ayarlar →
Uygulamalar → İsteğe bağlı özellikler → OpenSSH Sunucusu). Gerisi aynı:
`vmclaude add win10 --domain win10 --user KULLANICI`, `vmclaude setup win10`,
`vmclaude win10`. vmclaude Windows'u kendisi tanır. Kurulum Git for Windows'u
ve Claude Code'u kurar; SSH ile girişte Claude'un açılması için kullanıcının
PowerShell çalıştırma ilkesini `RemoteSigned` yapar. Windows'ta tmux olmadığı
için bağlantı kapanınca Claude oturumu da kapanır (`claude --continue` ile
konuşmaya devam edebilirsin).

**Notlar:** Otomatik başlatma yalnızca libvirt VM'lerinde çalışır. VirtualBox gibi diğer VM'leri kendin
başlatıp `--host`/`--port` ver. Telefondan erişmek için VM'in ağdan
erişilebilir olması gerekir (köprü ağ, port yönlendirme ya da Tailscale).

---

If vmclaude saved you some setup time, a ⭐ on GitHub helps others find it.
