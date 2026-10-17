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

Or do it all in a **terminal UI**: `vmclaude ui`. Pick the system, RAM, CPUs,
disk, the AI assistants (Claude Code, Codex, Gemini CLI, aider) and the ports
you want, then open, start, stop, snapshot, undo and resize your VMs from one
list. See [Terminal UI](#terminal-ui).

![vmclaude ui](docs/ui.png)

You can also skip the command. After setup, **any SSH login to the VM opens
Claude Code directly**: a terminal, a phone SSH app, PuTTY, Termius. There is
also an app-menu launcher.

> Türkçe açıklama aşağıda — [Türkçe](#türkçe).

## Features

- **One command:** `vmclaude` (or `vmclaude NAME`) connects and opens Claude.
- **Terminal UI:** `vmclaude ui` makes and manages VMs from one screen.
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
- **…and the VM shuts down when you are done:** quit Claude and a libvirt VM
  powers off (autostop), unless something still uses it: Claude left running
  with `Ctrl-b d`, another `vmclaude shell` or `mount`, an SSH login. Then it
  stays on and tells you why. `vmclaude stop NAME` / `start NAME` by hand,
  `--keep` once, `vmclaude autostop NAME off` for good. A VM nobody uses
  shuts itself down after 30 minutes (`vmclaude idle`).
- **Undo:** each start takes a snapshot first, so `vmclaude undo NAME` puts
  the VM back to how it was before Claude's session. See [Undo](#undo).
- **Notifications:** when Claude on the VM asks for permission or waits for
  you, a desktop notification appears on your computer, also after you
  detached. See [Notifications](#notifications).
- **Your browser, the VM's server:** `vmclaude open NAME 3000` makes a port
  of the VM a port here and opens it. See [Open a port](#open-a-port).
- **Copy on the VM, paste here:** what Claude copies, or what you copy in
  tmux, lands in your computer's clipboard. See [Clipboard](#clipboard).
- **Codex, Gemini CLI, aider:** `vmclaude NAME --codex` opens another agent
  the same way, installed on first use. See [Other agents](#other-agents).
- **One-step setup:** `vmclaude setup NAME` creates an SSH key and installs it
  on the VM (you type the VM password once). It installs tmux with the VM's
  package manager and Claude Code with the official installer.
- **Autostart on SSH login:** a small hook in `~/.bashrc` / `~/.zshrc` on the
  VM opens Claude on interactive SSH logins. Quit Claude (or press `Ctrl-b d`)
  to get a normal shell.
- **App-menu launcher:** `vmclaude desktop NAME`.
- **`vmclaude doctor`** checks each step: VM state, IP, sshd, key login,
  Claude, tmux, autostart.
- **Work in the VM from Claude Code on your computer:** `vmclaude mcp NAME --add`
  gives the Claude Code you already use tools to run commands and read, write
  and edit files inside the VM. See [Claude Code on your computer](#claude-code-on-your-computer-working-in-the-vm).
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
vmclaude login dev          # log Claude in (your browser, on this computer)
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

Log Claude in on the VM once, from your computer:

```sh
vmclaude login dev
```

This runs `claude setup-token` on your computer, where your browser is, takes
the long-lived token it prints and stores it on the VM in
`~/.config/vmclaude/claude-env` (readable only by your user there). Claude on
the VM uses it however it is started, so it never shows its login screen,
whose long link is hard to copy out of a terminal. It needs Claude Code on
your computer and a Claude subscription; an API key works too
(`echo "$ANTHROPIC_API_KEY" | vmclaude login dev`). Such tokens are for
chatting and coding only; for other account features use `/login` inside
Claude. `vmclaude login dev --remove` deletes the token again.

### Ways in

| From | How |
|---|---|
| Terminal | `vmclaude` (default VM) or `vmclaude dev` |
| App menu | `vmclaude desktop dev` adds **Claude Code (dev)** |
| Any SSH client | `ssh dev@VM` opens Claude (autostart) |
| A shell, not Claude | `vmclaude shell dev`, or quit Claude / `Ctrl-b d` |

### When you leave

With a libvirt VM, quitting Claude (`/exit`, or `Ctrl-C` twice) shuts the VM
down, the clean way (ACPI, like its power button), and waits until it is off.
It stays on, and says why, when something still uses it:

- Claude still runs in tmux because you detached with `Ctrl-b d`
  (`vmclaude dev` takes you back);
- another vmclaude connection to it is open on this computer
  (`vmclaude shell`, `vmclaude mount`, a second `vmclaude dev`);
- someone is logged in on the VM (an SSH login; on Windows, the screen),
  or a Claude process still runs there;
- the connection broke instead of ending.

`vmclaude dev --keep` leaves it on this time, `vmclaude autostop dev off`
always. `vmclaude stop dev` shuts it down by hand (`--force` pulls the plug),
`vmclaude start dev` boots it ahead of time, and `vmclaude list` shows which
VMs are running. Machines added with `--host` only are never shut down.

**…and when you forget.** `vmclaude idle dev 30` installs a small service on
the VM that shuts it down after 30 minutes in which nothing used it
(`vmclaude create` sets this up by itself). It covers what vmclaude on your
computer cannot see: Claude left running in tmux that finished long ago, a
plain `ssh` login that ended, a VM you forgot. Used means an SSH session
(shell, command or mount), a console login, Claude Code working (from its
hooks, see below) or a busy CPU on Linux; an SSH connection, someone signed
in on the screen or Claude running on Windows. Claude waiting for you counts
as unused: its conversation is saved, and `vmclaude dev --continue` resumes
it. Linux VMs need systemd and sudo; on Windows a scheduled task runs as
SYSTEM. `vmclaude idle dev off` removes it.

### Undo

Before vmclaude starts a libvirt VM that is off, it takes a snapshot
(`auto-DATE-TIME`; instant, since the VM is off). If Claude broke something:

```sh
vmclaude undo dev            # back to before this session (asks first)
vmclaude snapshots dev       # all snapshots, oldest first
vmclaude undo dev auto-20261016-224745
vmclaude snapshot dev "before the big refactor"   # one of your own, any time
```

The newest 3 automatic snapshots are kept (`vmclaude autosnap dev 10`, or
`off`); your own are never deleted automatically (`vmclaude snapshot dev
--delete NAME`). They are libvirt internal snapshots, stored inside the VM's
qcow2 disk, and grow with what changes after them. A snapshot of a running
VM includes its memory and returns to it running.

### Notifications

While Claude runs on the VM, `vmclaude dev` also starts a small
background process here that asks the VM every 15 seconds whether Claude
needs you: it asked for a permission, or it finished and waited a minute for
your answer. Then a desktop notification appears ("Claude Code (dev)").
It keeps going after you detach with `Ctrl-b d`, and stops when Claude ends
or the VM shuts down.

On the VM this uses Claude Code hooks, in two files that `vmclaude dev`
keeps in `~/.config/vmclaude/`: `hook.sh` and `claude-settings.json`, which
vmclaude passes to Claude with `--settings`. Your own
`~/.claude/settings.json` is not changed. The same hooks tell the idle
shutdown whether Claude is working. On Windows VMs Claude Code runs hooks
with Git Bash, so the same `hook.sh` works there. Needs `notify-send` on your
computer; `vmclaude notify dev off` turns it off.

### Open a port

Claude started a web server on the VM, say on port 3000:

```sh
vmclaude open dev 3000        # http://localhost:3000 here, opens in your browser
vmclaude open dev 5173 8080   # several
vmclaude open dev 9000:3000   # the VM's 3000 as localhost:9000
```

It is an SSH port forward, so it also works when the server listens only on
the VM's `localhost`, and for VMs elsewhere. A port taken here moves to the
next free one (it says which). `Ctrl-C` ends it; then the VM shuts down if
nothing else uses it (`--keep`: leave it on).

### Clipboard

While you are connected to Claude's tmux session on a Linux VM, what lands
in a tmux paste buffer lands in your computer's clipboard too: text Claude
Code copies (inside tmux it uses `tmux load-buffer`) and what you copy in
tmux copy mode. A second SSH session watches the buffers while you are
connected. Needs `xclip` or `xsel` (X11), `wl-copy` (Wayland) or `pbcopy`
here; `vmclaude clipboard dev off` turns it off. Terminals that understand
OSC 52 (kitty, WezTerm, foot, iTerm2, Windows Terminal) also get it from
tmux directly; VTE terminals (GNOME Terminal, Xfce Terminal) do not, which
is why vmclaude does it this way.

### Other agents

```sh
vmclaude dev --codex          # OpenAI Codex CLI
vmclaude dev --gemini         # Google Gemini CLI
vmclaude dev --aider          # aider
vmclaude agent dev codex      # make it the default for "vmclaude dev"
```

The agent is installed on the VM the first time, for the user in
`~/.local/bin`: Codex and aider with their own installers, Gemini CLI with
npm (Node.js 20+ comes from the package manager when missing). Each runs in
its own tmux session, so Claude's stays as it is, and gets the same
autostop, idle shutdown, snapshots and clipboard. Log in inside the agent
once: Codex's "Sign in with ChatGPT" completes in the browser here (vmclaude
forwards its port 1455). API keys can go into
`~/.config/vmclaude/codex-env` (or `gemini-env`, `aider-env`) on the VM as
lines like `OPENAI_API_KEY=...` or `GEMINI_API_KEY=...`. Notifications are for
Claude only, and other agents for Linux VMs only.

Skip autostart for one login with `ssh -o SetEnv=LC_VMCLAUDE=off dev@VM`. This
works with the default `AcceptEnv LANG LC_*` of Debian and Ubuntu. Turn
autostart off with `vmclaude autostart dev off`.

To reach the VM from **another device** (your phone, for example): a libvirt NAT
network (`192.168.122.x`) is reachable only from the host. Use a bridged
network, a port forward on the host, or a VPN such as Tailscale on the VM.

## Terminal UI

```sh
vmclaude ui
```

The list shows your VMs with state, RAM, CPUs, AI assistants and ports; the
right side, the details of the selected one. `n` opens the form for a new VM:

![New VM](docs/ui-new.png)

It shows the `vmclaude create` command line it is going to run, then the
output while the VM is made (download, cloud-init, tmux, the assistants), and
offers to open it or to log Claude in.

| Key | |
|---|---|
| `Enter` | open the VM's AI assistant (the UI steps aside until you quit it) |
| `a` | open another one: Claude Code, Codex, Gemini CLI, aider |
| `n` | new VM |
| `o` | ports: forward them now (`o` again stops), every time you connect, or to your LAN too |
| `t` / `s` / `l` | start or stop / shell / log Claude in |
| `p` / `u` | snapshot / undo (pick the snapshot) |
| `r` | RAM and CPUs (shuts the VM down first) |
| `d` | delete (type the name to confirm; profiles of VMs not made by vmclaude are only removed) |
| `q` | quit (stops the port forwards the UI started) |

The UI only runs this `vmclaude` and reads its `--json` output, so everything
it does works from the command line too. It is a [Textual](https://textual.textualize.io/)
app inside the same script: it needs Python 3 with Textual 8, which
`vmclaude ui` fetches by itself when [uv](https://docs.astral.sh/uv/) is
installed (or `pip install --user 'textual>=8'`).

## Commands

```
vmclaude                         connect to the default VM (asks to add one if none)
vmclaude NAME [CLAUDE_ARGS...]   connect to VM NAME, e.g. vmclaude dev --continue
vmclaude ui                      a terminal UI for all of this
vmclaude create NAME [options]   make a new Linux VM and set it up
    --image debian13|debian12|ubuntu24.04|arch  --memory MB  --cpus N  --disk GB
    --agents claude,codex,gemini,aider  --ports 3000,5173
    --user USER  --uri LIBVIRT_URI  --idle MINUTES|off  --no-setup
vmclaude resize NAME [--memory MB] [--cpus N] [--stop]
vmclaude delete NAME [--yes]     delete a VM made with create, and its disk
vmclaude images                  which images exist, are downloaded, used, and where
vmclaude prune                   remove downloaded images no VM uses any more
vmclaude add NAME [options]      add an existing VM, or change fields of a profile
    --host HOST  --user USER  --port PORT  --key FILE
    --domain LIBVIRT_DOMAIN  --uri LIBVIRT_URI  --dir DIR_ON_VM
    --session TMUX_SESSION  --no-tmux
vmclaude setup NAME [--agents LIST] [--no-install] [--no-autostart]
vmclaude connect [--keep] [--hold] [--no-tmux] [NAME] [-- CLAUDE_ARGS...]
vmclaude NAME --codex|--gemini|--aider|--claude [ARGS...]   another agent this time
vmclaude open [NAME] [PORT...]   the VM's port here, in your browser ([LOCAL:]PORT; --lan)
vmclaude ports NAME 3000,5173    ports forwarded each time you connect (off: none)
vmclaude shell [--keep] NAME [CMD...]   plain shell or command on the VM
vmclaude start NAME              boot a libvirt VM and wait for SSH
vmclaude stop NAME [--force]     shut a libvirt VM down
vmclaude autostop NAME on|off    shut the VM down when you leave Claude (default on)
vmclaude idle NAME MINUTES|off   the VM shuts itself down when unused (create sets 30)
vmclaude undo NAME [SNAPSHOT]    back to before this session (or to SNAPSHOT)
vmclaude snapshot NAME [NOTE]    take a snapshot; snapshots NAME lists them
vmclaude autosnap NAME N|off     automatic snapshots to keep (default 3)
vmclaude notify NAME on|off      desktop notifications when Claude needs you
vmclaude clipboard NAME on|off   copies in tmux on the VM land in this clipboard
vmclaude agent NAME [AGENT]      claude, codex, gemini or aider for "vmclaude NAME"
vmclaude autostart NAME on|off
vmclaude doctor NAME
vmclaude login NAME [--remove]   log Claude in on the VM with this computer's browser
vmclaude mcp NAME [--add]        tools for Claude Code on this computer to work in the VM
vmclaude mount NAME [FOLDER]     the VM's folder as a folder here (~/vm/NAME); umount NAME
vmclaude list [--json] | default NAME | desktop NAME | edit NAME | forget NAME | rm NAME
```

Claude arguments apply when a new tmux session starts. An existing session is
reattached as it is.

Every command has its own help with options and examples:
`vmclaude help create`, or `vmclaude create --help`.

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
AGENT=claude            # or codex, gemini, aider
AGENTS=claude,codex     # installed on the VM (noted by setup and vmclaude)
PORTS=3000,5173         # forwarded to this computer while connected
AUTOSTOP=on             # off: the VM keeps running after you leave Claude
AUTOSNAP=3              # automatic snapshots to keep; 0 = none
IDLE=30                 # what "vmclaude idle" set up on the VM (0 = off)
NOTIFY=on               # desktop notifications
CLIPBOARD=on            # copies on the VM land in this computer's clipboard
```

Environment: `VMCLAUDE_CONFIG_DIR` (another config folder),
`VMCLAUDE_BOOT_TIMEOUT` (seconds to wait for the VM, default 180),
`VMCLAUDE_STOP_TIMEOUT` (seconds to wait for a shutdown, default 120).

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

Where the files are (`vmclaude images` shows them with sizes and the VMs that
use each image):

| What | Where |
|---|---|
| Downloaded images | `~/.cache/vmclaude/images/` |
| Base images, one per image release | `/var/lib/libvirt/images/vmclaude-base-IMAGE-CHECKSUM.qcow2` |
| Each VM's own disk (only its differences) | `/var/lib/libvirt/images/NAME.qcow2` |
| Each VM's cloud-init settings | `/var/lib/libvirt/images/NAME-seed.iso` |

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

## Claude Code on your computer, working in the VM

Besides running Claude inside the VM, you can let the Claude Code on your own
computer reach into the VM. Register the VM once:

```sh
vmclaude mcp arch --add      # = claude mcp add --scope user arch -- vmclaude mcp arch
```

Every Claude Code session then has four more tools (see `/mcp`):

| Tool | Does, inside the VM |
|---|---|
| `run` | run a command: bash on Linux, PowerShell on Windows; output and exit code come back |
| `read_file` | read a file, with line numbers |
| `write_file` | create or overwrite a file; folders are created |
| `edit_file` | replace exact text, like Claude's own Edit tool |

Ask in plain words, e.g. *"in the arch VM, write ~/work/app.py and run it"*.
Paths are relative to the profile's `DIR` (or the home folder). The VM is
started when a tool needs it. Files travel over SFTP, so their size and
contents (any characters) do not matter. Remove with
`claude mcp remove arch --scope user`.

On Windows VMs, `.ps1` files with non-ASCII text are saved with a UTF-8 BOM,
because Windows PowerShell 5.1 would read them in the old ANSI code page
otherwise; and any non-zero exit code shows as 1 (see [Windows VMs](#windows-vms)).

### Or: the VM's folder as a local folder

```sh
vmclaude mount arch          # ~/vm/arch is now the VM's working folder (sshfs)
cd ~/vm/arch && claude       # Claude Code edits the VM's files with its normal tools
vmclaude umount arch
```

Needs `sshfs` (`sudo apt install sshfs`). Mind that commands started in that
folder still run on your computer; run things in the VM with
`vmclaude shell arch 'make test'` or with the `run` tool above. Works with
Linux and Windows VMs.

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
- `tests/test_login.py` checks that the token reaches Claude however it is
  started (tmux, autostart, a shell, Windows) and never appears on a command
  line.
- `tests/test_mount.py` checks `mount`/`umount` with a fake sshfs.
- `tests/test_mcp.py` talks MCP to `vmclaude mcp` the way Claude Code does
  and checks every tool against a throwaway VM home.
- `tests/test_create.py` runs `create` and `delete` against fake `curl`,
  `virsh` and `virt-install`, including that `delete` refuses VMs it did not
  create.
- `tests/test_windows.py` checks OS detection and decodes the PowerShell
  commands sent to Windows VMs.
- `tests/test_stop.py` covers autostop, `start` and `stop`: every reason to
  keep a VM on, with the Linux check really running against fake
  `tmux`/`who`/`pgrep`.
- `tests/test_snapshots.py` covers automatic snapshots and their pruning,
  `snapshot`, `snapshots` and `undo` (including its question) against a fake
  `virsh` that keeps snapshots.
- `tests/test_idle_notify.py` runs `hook.sh` with Claude's hook input, the
  watcher against a fake VM (new events become notifications, it stops when
  Claude is gone, one per VM), and checks the idle installers.
- `tests/test_ui.py` drives the terminal UI with Textual's test pilot
  against a fake `vmclaude`: the list, the new-VM form and its checks, every
  key. It needs Textual (`uv run --with 'textual>=8,<9' python -m unittest
  tests.test_ui`), else it is skipped. `tests/test_ui_backend.py` covers what
  it builds on: `list`/`images`/`snapshots --json`, `ports`, `create`/`setup
  --agents`, `resize` and `open --lan`.
- By hand, the UI on this computer's libvirt: a new Arch VM with Claude Code,
  Codex and port 8000 made from the form (the port reached here while
  connected, gone after detaching), then RAM and CPUs changed, and the VM
  deleted, all from the UI.
- `tests/test_extras.py` covers `open` (a fake ssh that really listens on
  the forwarded port; Ctrl-C on a pseudo-terminal), the clipboard script
  against a fake tmux and its way into a fake `xclip`, the agents (sessions,
  installing a missing one, Claude's settings for Claude only) and the
  Windows hooks and watcher.
- By hand, on the Arch VM: `vmclaude open` with a Python web server on the
  VM (fetched here, Ctrl-C, VM off); the clipboard with real tmux (a
  `tmux load-buffer -w`, as Claude Code does it, with Turkish letters, and a
  copy-mode buffer, both arrived here; nothing left running after detaching);
  `--codex`, `--gemini` and `--aider` installing and starting each agent, and
  Codex's login page reachable through the forwarded port 1455. On the
  Windows 10 VM: a real Claude session whose hooks ran under Git Bash, and
  the notification "work: Claude is waiting for your input" here.
- By hand, the hooks in real Claude Code 2.1: `UserPromptSubmit`,
  `PreToolUse`, `PostToolUse` and `Stop` in a `claude -p` run, and the
  Notification "Claude is waiting for your input" in an interactive one.
- By hand, on the Arch VM: idle shutdown after 1 minute and none while an
  SSH session was open (the watcher's polls do not count); a snapshot at each
  start, `undo` removing a file written after it, a live snapshot and undo to
  it; a notification from the watcher. On the Windows 10 VM: snapshots, and
  the idle task shutting it down 2 minutes after the last connection.
- By hand, autostop on the Arch VM (quit Claude, exit `vmclaude shell`: off;
  `Ctrl-b d`, a second connection, an SSH login: stays on) and on the
  Windows 10 VM (quit Claude: off within seconds).
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
- By hand, `vmclaude mcp` against the Arch and Windows 10 VMs, and a real
  `claude -p` session that wrote, ran, edited and re-ran a program in the
  Arch VM using only these tools. `vmclaude mount` with both VMs: files
  written on either side show up on the other.
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
- Only libvirt VMs are started and shut down automatically. A plain `ssh`
  login (autostart) never shuts the VM down: vmclaude is not running then
  (the idle shutdown does, later).
- Snapshots need a qcow2 disk and libvirt. The clipboard and other agents
  need a Linux VM (tmux).
- Only libvirt starts, stops and snapshots VMs. Other hypervisors (VirtualBox,
  VMware, Hyper-V, a cloud VM) work through `--host`: connect, open, clipboard,
  notifications, idle shutdown; start them yourself.
- The idle shutdown cannot see long jobs outside Claude that use little CPU
  (a download, a `sleep`); give it more minutes or turn it off for those.

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
`vmclaude images` hangi imajların indiğini, nerede durduğunu ve hangi VM'lerin
kullandığını gösterir. Her komutun örnekli yardımı var: `vmclaude help create`.

**Var olan bir VM ile kurulum ve ilk kullanım:**

```sh
git clone https://github.com/emincan2000/vmclaude && cd vmclaude && ./install.sh

vmclaude add dev --domain debian13 --user dev   # libvirt VM'i (otomatik başlar, IP'si bulunur)
# ya da: vmclaude add dev --host 192.168.1.50 --user dev
vmclaude setup dev    # SSH anahtarı + tmux + Claude Code + otomatik başlatma (VM şifresi bir kez sorulur)
vmclaude              # Claude Code'u VM'de aç
```

Argümansız `vmclaude` ilk seferde VM bilgilerini sorar ve kurulumu teklif eder.
Claude'a VM'de giriş için `vmclaude login dev` çalıştır: giriş senin
bilgisayarında, tarayıcında olur; vmclaude oluşan token'ı VM'e kendisi taşır.
Böylece VM'de giriş ekranı ve kopyalanması zor bağlantı hiç çıkmaz.

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

**Çıkınca VM kapanır:** libvirt VM'lerinde Claude'dan çıkınca (`/exit` ya da
iki kez `Ctrl-C`) VM düzgünce kapatılır. Hâlâ kullanılıyorsa açık kalır ve
nedenini söyler: `Ctrl-b d` ile Claude'u arkada bıraktıysan, açık bir
`vmclaude shell` / `mount` ya da başka bir SSH girişi varsa. Bir seferlik açık
bırakmak: `vmclaude dev --keep`; hiç kapatmamak: `vmclaude autostop dev off`.
Elle: `vmclaude stop dev` (`--force` fişi çeker), `vmclaude start dev`.
`vmclaude list` hangi VM'in açık olduğunu gösterir.

**Unutursan da kapanır:** `vmclaude idle dev 30` VM'e küçük bir servis kurar;
VM 30 dakika boyunca kullanılmazsa (SSH oturumu yok, Claude çalışmıyor, işlemci
boşta) kendini kapatır. `vmclaude create` bunu kendisi kurar. Kapatmak için:
`vmclaude idle dev off`.

**Geri alma:** vmclaude kapalı bir VM'i her açmadan önce anlık görüntüsünü
alır. Claude bir şeyi bozduysa `vmclaude undo dev` VM'i bu oturumdan önceki
hâline döndürür (önce sorar). `vmclaude snapshots dev` hepsini listeler,
`vmclaude snapshot dev "not"` istediğin an bir tane alır. Son 3 otomatik
görüntü saklanır (`vmclaude autosnap dev 10` ya da `off`).

**Bildirimler:** Claude VM'de senden izin istediğinde ya da işini bitirip
cevabını beklediğinde bilgisayarında masaüstü bildirimi çıkar; `Ctrl-b d` ile
ayrıldıktan sonra da; Windows VM'lerinde de. Kapatmak için:
`vmclaude notify dev off`.

**VM'deki sunucu tarayıcında:** Claude VM'de bir web sunucusu açtıysa
`vmclaude open dev 3000` onu bilgisayarında `http://localhost:3000` olarak
açar. Port doluysa bir sonrakini kullanır. `Ctrl-C` ile biter.

**Pano:** Claude'un VM'de kopyaladığı ya da tmux'ta kopyaladığın metin
bilgisayarının panosuna gelir (bilgisayarında `xclip` gerekir). Kapatmak için:
`vmclaude clipboard dev off`.

**Terminal arayüzü:** `vmclaude ui` her şeyi tek ekranda toplar. `n` ile yeni
VM: sistem, RAM, işlemci, disk, kurulacak yapay zekâ yardımcıları (Claude
Code, Codex, Gemini CLI, aider) ve açılacak portlar seçilir; arayüz aynı işi
yapan `vmclaude create` komutunu da gösterir. Listede `Enter` seçili VM'de
yardımcıyı açar; `o` portlar, `t` başlat/durdur, `p` anlık görüntü, `u` geri
alma, `r` RAM/işlemci, `d` silme (adını yazarak onaylanır). Python ve Textual
gerekir; `uv` kuruluysa vmclaude Textual'ı kendisi getirir.

**Diğer araçlar:** `vmclaude dev --codex`, `--gemini` ya da `--aider` Claude
yerine o aracı açar; ilk seferde VM'e kendisi kurar. Kalıcı yapmak için:
`vmclaude agent dev codex`. Codex'in "Sign in with ChatGPT" girişi
bilgisayarındaki tarayıcıda tamamlanır.

**Bilgisayarındaki Claude Code'dan VM'e müdahale:** `vmclaude mcp arch --add`
bir kez çalıştırınca, kendi bilgisayarındaki Claude Code'a VM'in içinde komut
çalıştırma, dosya okuma, yazma ve düzenleme araçları eklenir. Sonra Claude'a
"arch VM'inde ~/work/app.py yaz ve çalıştır" demen yeterli.
Ya da `vmclaude mount arch` ile VM'in klasörünü `~/vm/arch` olarak bağlayıp
Claude Code'u orada açabilirsin; dosyalar doğrudan VM'de değişir (komutlar ise
bilgisayarında çalışır, VM'de çalıştırmak için `vmclaude shell`).

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

**Notlar:** Otomatik başlatma, kapatma ve geri alma yalnızca libvirt
VM'lerinde çalışır. VirtualBox, VMware ya da Hyper-V gibi diğer VM'leri kendin
başlatıp `--host`/`--port` ver; bağlantı, port açma, pano ve bildirimler
onlarda da çalışır. Telefondan erişmek için VM'in ağdan
erişilebilir olması gerekir (köprü ağ, port yönlendirme ya da Tailscale).

---

If vmclaude saved you some setup time, a ⭐ on GitHub helps others find it.
