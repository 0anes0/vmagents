<div align="center">
  <h1>vmagents</h1>
  <p><i>Run AI coding agents inside a virtual machine, not on your computer</i></p>

  **English** · [Türkçe](README.tr.md)

  ![Bash](https://img.shields.io/badge/bash-4+-4EAA25.svg)
  ![License](https://img.shields.io/badge/license-MIT-green.svg)
  ![Host](https://img.shields.io/badge/host-Linux-lightgrey.svg)
  ![VMs](https://img.shields.io/badge/VMs-Linux%20%7C%20Windows-lightgrey.svg)
  ![Agents](https://img.shields.io/badge/agents-Claude%20Code%20%7C%20Codex%20%7C%20Gemini%20%7C%20OpenCode%20%7C%20aider-blueviolet.svg)
  ![Languages](https://img.shields.io/badge/UI-EN%20%7C%20TR-orange.svg)
  [![test](https://github.com/emincan2000/vmagents/actions/workflows/test.yml/badge.svg)](https://github.com/emincan2000/vmagents/actions/workflows/test.yml)

  [Install](#install) · [Quick start](#quick-start) · [Terminal UI](#terminal-ui) · [Projects](#projects) · [Commands](#commands)
</div>

---

**vmagents** runs Claude Code, Codex, Gemini CLI, OpenCode or aider **inside a
virtual machine** with one command. It starts the VM if needed, connects over
SSH and opens the agent there: in tmux on **Linux** VMs (Claude Code also on
**Windows** VMs). The agent works on the VM's files and programs, not your
computer's: let it install, run and break things, then take it all back with
`vmagents undo`.

```
$ vmagents
Starting VM dev...
Waiting for dev to get an IP address...
Waiting for SSH on 192.168.122.48:22...
 ╭──────────────────────────────────────╮
 │ ✻ Welcome to Claude Code!            │     ← running on the VM, in tmux
```

No VM yet? `vmagents create dev` makes a fresh Debian VM with Claude Code in
it, usually in half a minute to two minutes once the image is downloaded,
without a single password prompt. Or do everything from the **terminal UI**,
`vmagents ui`:

![vmagents ui](docs/ui.png)

> vmagents was called **vmclaude** until 0.10. The old command still works,
> and the first run moves its settings over by itself.

## Features

| | |
|---|---|
| **One command** | `vmagents` (or `vmagents NAME`) starts the VM, connects and opens the agent. |
| **Terminal UI** | `vmagents ui`: make VMs (system, RAM, CPUs, disk, agents, ports), open shells and agents in tabs, snapshots, ports, projects. |
| **Your project, back as a branch** | `vmagents project` sends a git repository to the VM, `vmagents take` brings the agents' work back as a branch or pull request. No GitHub keys on the VM. |
| **New VMs on demand** | `vmagents create` builds a libvirt VM from an official cloud image (Debian 13, Debian 12, Ubuntu 24.04, Arch Linux). |
| **Undo** | Every start takes a snapshot first; `vmagents undo` puts the VM back to before the session. |
| **Sessions survive disconnects** | The agent runs in tmux. Lose Wi-Fi, connect again: same session. |
| **Shuts down when you are done** | Quit the agent and the VM powers off, unless something still uses it. Forgotten VMs shut themselves down after 30 idle minutes. |
| **Notifications** | A desktop notification when Claude on the VM asks for permission or waits for you. |
| **The VM's server in your browser** | `vmagents open dev 3000` makes the VM's port 3000 a port here. |
| **Shared clipboard** | What Claude (or you, in tmux) copies on the VM lands in your clipboard. |
| **Five agents** | Claude Code, Codex, Gemini CLI, OpenCode, aider; installed on first use. |
| **One-step setup** | `vmagents setup` installs the SSH key (you type the VM password once), tmux, git and Claude Code. |
| **Any SSH login opens Claude** | A terminal, a phone SSH app, PuTTY, Termius; plus an app-menu launcher. |
| **Claude Code here, working there** | `vmagents mcp NAME --add` gives the Claude Code on your computer tools to run and edit things in the VM. |
| **Windows VMs too** | Detected from the SSH banner; setup installs Git for Windows and Claude Code. |
| **`vmagents doctor`** | Checks each step: VM state, IP, sshd, key login, Claude, tmux, autostart. |

A single Bash script with no dependencies beyond OpenSSH (and virsh for
libvirt VMs, Python for the UI). Several VMs, one default, plain-text profiles.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/emincan2000/vmagents/main/install.sh | bash
```

or from a clone: `git clone https://github.com/emincan2000/vmagents && cd vmagents && ./install.sh`.
It puts `vmagents` in `~/.local/bin`; `./install.sh --uninstall` removes it.

**Requirements**

- **Your computer:** Linux, bash 4+, the OpenSSH client. `virsh` for libvirt
  VMs. The UI needs Python 3 with Textual and pyte, which `vmagents ui` fetches
  by itself when [uv](https://docs.astral.sh/uv/) is installed.
- **A Linux VM:** an SSH server, `curl`, and a user that can log in with a
  password once (or already has your key). `sudo` only to install packages.
- **A Windows VM:** Windows 10 1809+ or 11 with OpenSSH Server; see
  [Windows VMs](#windows-vms).

Any VM works: libvirt/virt-manager/GNOME Boxes (qemu), VirtualBox, VMware,
Proxmox, a cloud server. Only libvirt VMs are started, stopped and
snapshotted by vmagents; start the others yourself and give their address.

## Quick start

**From nothing** (Linux with libvirt):

```sh
vmagents create dev         # new Debian VM + Claude Code, no password needed
vmagents login dev          # log Claude in (your browser, on this computer)
vmagents dev                # open Claude Code in it
```

**With a VM you already have:** run `vmagents` with no arguments; the first
time it asks for the VM's details and offers to set it up. Or by hand:

```sh
vmagents add dev --domain debian13 --user dev              # a libvirt VM: started on demand, IP found
vmagents add dev --host 192.168.1.50 --user dev            # any other VM
vmagents add vbox --host 127.0.0.1 --port 2222 --user dev  # VirtualBox NAT forward
vmagents setup dev          # key, tmux, git, Claude Code, autostart
vmagents                    # open Claude Code on the VM
```

**Logging Claude in:** `vmagents login dev` runs `claude setup-token` on your
computer, where your browser is, and stores the long-lived token on the VM in
`~/.config/vmagents/claude-env` (readable only by you there). Claude on the VM
then never shows its login screen, whose long link is hard to copy out of a
terminal. It needs Claude Code here and a Claude subscription; an API key
works too (`echo "$ANTHROPIC_API_KEY" | vmagents login dev`). These tokens are
for chatting and coding; for other account features use `/login` in Claude.
`vmagents login dev --remove` deletes it.

| Ways in | |
|---|---|
| Terminal | `vmagents` (default VM) or `vmagents dev` |
| App menu | `vmagents desktop dev` adds **Claude Code (dev)** |
| Any SSH client | `ssh dev@VM` opens Claude (autostart) |
| A shell, not Claude | `vmagents shell dev`, or quit Claude / `Ctrl-b d` |

Every command has its own help with examples: `vmagents help create`.

## Terminal UI

```sh
vmagents ui
```

The list shows your VMs with state, RAM, CPUs, agents and ports; the right
side, the selected one's details. Everything works from the keyboard, with
Vim keys too (`j`/`k` move, `l` or Enter open, `h` or Esc back).

- **New VM** (`n`): choose the system, RAM, CPUs, disk, agents, ports and a
  project. The form shows the `vmagents create` command it runs; the VM is
  then made in a tab of its own while the list stays usable.
- **Opening a VM** (Enter) asks how: a shell or one of the agents. It opens
  **inside the UI**, in a terminal tab; F1 to F6 open the others next to it.
- **One row of tabs:** the VM list first, then every terminal (on any VM),
  every VM being created and every project's changes. `Ctrl+]` goes to the
  list and back to the tab you were in.
- **Who needs you:** a terminal tab you are not looking at shows a spinner
  while its program works, and a dot (●) when it stops or rings: the agent
  finished or waits for you. The list marks that VM, and a message names the
  tab. It watches the terminal only, so it works for every agent and shells.

| New VM | Claude Code in a tab |
|---|---|
| ![New VM](docs/ui-new.png) | ![A shell and Claude Code in tabs](docs/ui-session.png) |

<details>
<summary><b>Keys</b></summary>

| On the list | |
|---|---|
| `j` / `k` | down / up |
| `Enter`, `l` | open: a shell or an agent, in a terminal tab |
| `s` | a shell on the VM, straight away |
| `n` | new VM |
| `p` / `c` | send a project (a git repository) / its changes, in a tab (`t` there: take as a branch, `P`: pull request) |
| `u` | snapshots: go back to one, take one with a name and a label, relabel, delete |
| `o` | ports: forward now (`o` again stops), every time you connect, or to your LAN too |
| `t` / `r` | start or stop / RAM and CPUs (shuts the VM down first) |
| `d` | delete (type the name to confirm; VMs not made by vmagents lose only their profile) |
| `L` | language: English, Türkçe (remembered) |
| `1` … `9` | that tab (1 is the list) |
| `Ctrl+]` | back to the tab you were in |
| `q` | quit (asks first when terminals are open or a VM is being created) |

| In a terminal tab | |
|---|---|
| `F1` | shell |
| `F2` … `F6` | Claude Code, Codex, Gemini CLI, OpenCode, aider |
| `Ctrl+]` | the list |
| `F7` / `F8` | previous / next tab (also `Ctrl+PgUp` / `Ctrl+PgDn`, where the terminal passes them on) |
| everything else | goes to the VM; the mouse wheel scrolls back |

</details>

The UI only runs `vmagents` and reads its `--json` output, so everything it
does works from the command line too. It is a
[Textual](https://textual.textualize.io/) app inside the same script, with
[pyte](https://github.com/selectel/pyte) as its terminal (or
`pip install --user 'textual>=8' pyte` without uv).

## Projects

Let the agents work on a repository of yours, in the VM, and take back what
they did as a branch:

```sh
vmagents project dev ~/code/app   # send it: ~/projects/app on the VM; agents start there
vmagents dev                      # ...the agent works (it may run anything: it is a VM)
vmagents changes dev              # what it changed: its commits, and what it did not commit
vmagents take dev                 # all that as the branch vmagents/dev in ~/code/app
git merge vmagents/dev            # or: vmagents take dev --pr (a pull request, with gh)
vmagents project dev              # send the result (and your new commits) back
```

- Commits travel as git bundles over vmagents's SSH connection: the VM needs
  no access to GitHub and no keys, and only committed work goes there.
- `take` makes or moves a branch only; your checkout is not touched.
  Uncommitted work on the VM (new files too, not ignored ones like
  `node_modules`) comes back as one extra commit on top of the agent's own.
- Sending again replaces the VM's copy, so it is refused while the VM has work
  that was not taken back; `--discard` sends anyway and keeps that work on the
  VM under `refs/vmagents/discarded/`.
- `vmagents create web --project ~/code/app` makes a VM with the project in it.
  In the UI: `p` sends, `c` shows the changes in a tab (`t` take, `P` pull request).

![The changes of a project, in a tab](docs/ui-changes.png)

## Everyday use

### When you leave

With a libvirt VM, quitting the agent (`/exit`, or `Ctrl-C` twice) shuts the
VM down the clean way (ACPI) and waits until it is off. It stays on, and says
why, when something still uses it:

- the agent still runs in tmux because you detached with `Ctrl-b d`
  (`vmagents dev` takes you back);
- another vmagents connection is open (`vmagents shell`, `mount`, a second `vmagents dev`);
- someone is logged in on the VM (SSH; on Windows, the screen), or Claude still runs there;
- the connection broke instead of ending.

`vmagents dev --keep` leaves it on this time, `vmagents autostop dev off`
always. `vmagents stop dev` shuts it down (`--force` pulls the plug),
`vmagents start dev` boots it ahead of time, `vmagents list` shows what runs.
Machines added with `--host` only are never shut down.

**…and when you forget:** `vmagents idle dev 30` installs a small service on
the VM that shuts it down after 30 minutes in which nothing used it (`create`
sets this up). Used means an SSH session, a console login, Claude working
(from its hooks) or a busy CPU on Linux; an SSH connection, someone signed in
or Claude running on Windows. Claude waiting for you counts as unused: its
conversation is saved and `vmagents dev --continue` resumes it. Linux VMs
need systemd and sudo; Windows uses a scheduled task. `vmagents idle dev off`
removes it.

### Undo

Before vmagents starts a libvirt VM that is off, it takes a snapshot
(`auto-DATE-TIME`; instant, since the VM is off). If the agent broke something:

```sh
vmagents undo dev                                  # back to before this session (asks first)
vmagents snapshots dev                             # all snapshots, oldest first
vmagents undo dev auto-20261016-224745
vmagents snapshot dev --name clean "before the big refactor"   # one of your own, any time
```

The newest 3 automatic snapshots are kept (`vmagents autosnap dev 10`, or
`off`); your own are never deleted automatically (`--delete NAME`). They are
libvirt internal snapshots inside the VM's qcow2 disk. A snapshot of a running
VM includes its memory and returns to it running.

### Notifications

While Claude runs on the VM, `vmagents dev` starts a small background process
here that asks the VM every 15 seconds whether Claude needs you (a permission
question, or finished and waiting a minute). Then a desktop notification
appears, "Claude Code (dev)". It keeps going after `Ctrl-b d` and stops when
Claude ends or the VM shuts down.

On the VM this uses Claude Code hooks in `~/.config/vmagents/` (`hook.sh` and
`claude-settings.json`, passed with `--settings`); your own
`~/.claude/settings.json` is not changed. On Windows VMs the hooks run under
Git Bash. Needs `notify-send` here; `vmagents notify dev off` turns it off.

### Open a port

```sh
vmagents open dev 3000        # http://localhost:3000 here, opens in your browser
vmagents open dev 5173 8080   # several
vmagents open dev 9000:3000   # the VM's 3000 as localhost:9000
vmagents ports dev 3000,5173  # forward these every time you connect
```

An SSH port forward: it works when the server listens only on the VM's
`localhost`, and for VMs elsewhere. A port taken here moves to the next free
one. `Ctrl-C` ends it, then the VM shuts down if nothing else uses it.

### Clipboard

While you are connected to a Linux VM's tmux session, what lands in a tmux
paste buffer lands in your clipboard too: text Claude Code copies and what
you copy in tmux copy mode. Needs `xclip` or `xsel` (X11), `wl-copy`
(Wayland) or `pbcopy` here; `vmagents clipboard dev off` turns it off.
(VTE terminals such as GNOME Terminal and Xfce Terminal do not understand
OSC 52, which is why vmagents does it this way.)

### Other agents

```sh
vmagents dev --codex          # OpenAI Codex CLI
vmagents dev --gemini         # Google Gemini CLI
vmagents dev --opencode       # OpenCode
vmagents dev --aider          # aider
vmagents agent dev codex      # make it the default for "vmagents dev"
```

Each agent is installed on the VM the first time (Codex, OpenCode and aider
with their own installers, Gemini CLI with npm), runs in its own tmux session
and gets the same autostop, idle shutdown, snapshots and clipboard. Log in
inside the agent once: Codex's "Sign in with ChatGPT" completes in the browser
here (vmagents forwards its port 1455). API keys can go into
`~/.config/vmagents/codex-env` (or `gemini-env`, `opencode-env`, `aider-env`)
on the VM. Notifications are for Claude only, other agents for Linux VMs only.

### Autostart and other devices

Any interactive SSH login opens Claude; quit it or press `Ctrl-b d` for a
shell. Skip it once with `ssh -o SetEnv=LC_VMAGENTS=off dev@VM`, turn it off
with `vmagents autostart dev off`. To reach the VM from **another device**
(your phone): a libvirt NAT network (`192.168.122.x`) is reachable only from
the host; use a bridged network, a port forward or a VPN such as Tailscale.

## Create a VM

```sh
vmagents create dev                                   # Debian 13, 4 GB RAM, 2 CPUs, 20 GB disk
vmagents create big --memory 16384 --cpus 8 --disk 100
vmagents create u --image ubuntu24.04
vmagents create a --image arch --agents claude,codex --ports 3000
vmagents delete dev                                   # asks you to type the name
vmagents prune                                        # free the space of unused images
```

Needs `virsh` and `virt-install`, and your user in the `libvirt` group:

| | |
|---|---|
| Debian / Ubuntu | `sudo apt install libvirt-daemon-system virtinst` |
| Arch | `sudo pacman -S libvirt virt-install libisoburn dnsmasq qemu-desktop` and `sudo systemctl enable --now libvirtd` |

If libvirt has no `default` storage pool yet (a fresh Arch), `create` makes
one in `/var/lib/libvirt/images`. With **ufw** on, allow the libvirt bridge
or the VM gets no IP address (vmagents says so when it happens):
`sudo ufw allow in on virbr0 && sudo ufw route allow in on virbr0 && sudo ufw route allow out on virbr0`.

What `create` does:

1. Downloads the official cloud image once into `~/.cache/vmagents/images`
   and checks it against the distribution's published SHA-512/SHA-256 sums.
2. Copies it into the libvirt pool `default` as a shared base volume. Each VM
   gets a thin copy-on-write disk on top, so a new VM takes seconds and little
   space.
3. Starts the VM with a cloud-init seed: your user with your vmagents SSH key
   and password-less `sudo` (the account has no password at all), and tmux.
4. Waits until the VM accepts the key, then runs `vmagents setup`.

| What | Where |
|---|---|
| Downloaded images | `~/.cache/vmagents/images/` |
| Base images, one per image release | `/var/lib/libvirt/images/vmagents-base-IMAGE-CHECKSUM.qcow2` |
| Each VM's own disk (only its differences) | `/var/lib/libvirt/images/NAME.qcow2` |
| Each VM's cloud-init settings | `/var/lib/libvirt/images/NAME-seed.iso` |

`vmagents images` shows them with sizes and the VMs that use each; `prune`
removes base volumes no VM is built on, and the download cache. The VM is on
libvirt's `default` NAT network and shows up in virt-manager like any other
(other pools or networks: `VMAGENTS_POOL`, `VMAGENTS_NETWORK`). Arch's image
comes from `geo.mirror.pkgbuild.com`; pick another mirror with
`VMAGENTS_ARCH_MIRROR` (the checksum still comes from Arch's own server).

`delete` only deletes VMs that `create` made: the profile has to say so, and
so does the VM's libvirt description ("created by vmagents").

<details>
<summary>Two details that real runs turned up</summary>

The seed is a virtio disk, not virt-install's `--cloud-init` CD-ROM, because
the Debian 12 cloud kernel has no driver for that SATA CD-ROM. And the VM gets
a video device even without a screen, because without one the GRUB of the
Debian cloud images resets the VM in a loop.

</details>

## Claude Code on your computer, working in the VM

Besides running Claude inside the VM, you can let the Claude Code on your own
computer reach into it:

```sh
vmagents mcp arch --add      # = claude mcp add --scope user arch -- vmagents mcp arch
```

Every Claude Code session then has four more tools (see `/mcp`):

| Tool | Does, inside the VM |
|---|---|
| `run` | run a command (bash on Linux, PowerShell on Windows); output and exit code come back |
| `read_file` | read a file, with line numbers |
| `write_file` | create or overwrite a file; folders are created |
| `edit_file` | replace exact text, like Claude's own Edit tool |

Ask in plain words, e.g. *"in the arch VM, write ~/work/app.py and run it"*.
Paths are relative to the profile's `DIR`; the VM is started when needed;
files travel over SFTP. Remove with `claude mcp remove arch --scope user`.

**Or the VM's folder as a local folder** (needs `sshfs`):

```sh
vmagents mount arch          # ~/vm/arch is now the VM's working folder
cd ~/vm/arch && claude       # Claude Code edits the VM's files with its normal tools
vmagents umount arch
```

Commands started in that folder still run on your computer; run things in
the VM with `vmagents shell arch 'make test'` or the `run` tool above.

## Windows VMs

Turn on the SSH server in Windows once, in an administrator PowerShell (or
Settings → Apps → Optional features → OpenSSH Server):

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd; Set-Service sshd -StartupType Automatic
```

Then it works as on Linux:

```sh
vmagents add win10 --domain win10 --user emin   # or --host IP
vmagents setup win10
vmagents win10
```

<details>
<summary>What is different on Windows</summary>

- **No tmux.** Closing the connection ends Claude's session; `claude
  --continue` picks the conversation up again.
- **setup** puts your key in `~\.ssh\authorized_keys`, and for administrators
  also in `C:\ProgramData\ssh\administrators_authorized_keys` (the only file
  Windows OpenSSH reads for them). It installs Git for Windows (winget, else
  the official installer from GitHub) and Claude Code the way
  `https://claude.ai/install.ps1` does, downloading with `curl.exe` because
  `Invoke-WebRequest` in PowerShell 5.1 times out on the 270 MB binary.
- **Autostart** goes into your PowerShell profile. That needs PowerShell as
  OpenSSH's default shell and an execution policy that runs profile scripts;
  a `Restricted` user policy is set to `RemoteSigned` (it says so).
  `vmagents shell NAME` opens PowerShell without Claude.
- Commands go as `powershell -EncodedCommand`, which works under `cmd.exe`
  and PowerShell alike. Claude's arguments pass through Windows' own
  command-line rules, so quotes, spaces and trailing backslashes arrive unchanged.
- Claude Code on Windows sometimes stays after you quit it under OpenSSH;
  vmagents notices the console switching back to line mode and ends it.

</details>

## Commands

```
vmagents                         connect to the default VM (asks to add one if none)
vmagents NAME [CLAUDE_ARGS...]   connect to VM NAME, e.g. vmagents dev --continue
vmagents NAME --codex|--gemini|--opencode|--aider [ARGS...]   another agent this time
vmagents ui                      the terminal UI

vmagents create NAME [options]   make a new Linux VM and set it up
    --image debian13|debian12|ubuntu24.04|arch  --memory MB  --cpus N  --disk GB
    --agents claude,codex,gemini,opencode,aider  --ports 3000,5173  --project DIR
    --user USER  --uri LIBVIRT_URI  --idle MINUTES|off  --no-setup
vmagents resize NAME [--memory MB] [--cpus N] [--stop]
vmagents delete NAME [--yes]     delete a VM made with create, and its disk
vmagents images | prune          downloaded images and where they are / remove unused ones

vmagents add NAME [options]      add an existing VM, or change fields of a profile
    --host HOST  --user USER  --port PORT  --key FILE
    --domain LIBVIRT_DOMAIN  --uri LIBVIRT_URI  --dir DIR_ON_VM
    --session TMUX_SESSION  --no-tmux
vmagents setup NAME [--agents LIST] [--no-install] [--no-autostart]
vmagents connect [--keep] [--hold] [--no-tmux] [NAME] [-- CLAUDE_ARGS...]
vmagents shell [--keep] NAME [CMD...]   plain shell or command on the VM
vmagents start NAME | stop NAME [--force]

vmagents project NAME [DIR]      send a git repository here to the VM (--discard, --off)
vmagents changes NAME [--stat]   what the agents changed in it there
vmagents take NAME [--branch B] [--pr]   that work as a branch here (or a pull request)

vmagents open [NAME] [PORT...]   the VM's port here, in your browser ([LOCAL:]PORT; --lan)
vmagents ports NAME 3000,5173    ports forwarded each time you connect (off: none)
vmagents undo NAME [SNAPSHOT]    back to before this session (or to SNAPSHOT)
vmagents snapshot NAME [--name SNAP] [LABEL]   take one; snapshots NAME lists them
vmagents snapshot NAME --label SNAP LABEL      change a snapshot's label
vmagents autosnap NAME N|off     automatic snapshots to keep (default 3)
vmagents autostop | autostart | notify | clipboard NAME on|off
vmagents idle NAME MINUTES|off   the VM shuts itself down when unused (create sets 30)
vmagents agent NAME [AGENT]      what "vmagents NAME" opens
vmagents login NAME [--remove]   log Claude in on the VM with this computer's browser
vmagents mcp NAME [--add]        tools for Claude Code here to work in the VM
vmagents mount NAME [FOLDER]     the VM's folder as a folder here; umount NAME
vmagents doctor NAME             check every step
vmagents list [--json] | default NAME | desktop NAME | edit NAME | forget NAME | rm NAME
```

Claude arguments apply when a new tmux session starts; an existing session is
reattached as it is. `vmagents help COMMAND` (or `COMMAND --help`) explains
each command with examples.

## Configuration

Profiles are plain `KEY=VALUE` files in `~/.config/vmagents/hosts/NAME.conf`,
parsed, never executed:

```
HOST=192.168.122.48     # optional with DOMAIN
USER=dev
PORT=22
IDENTITY=~/.ssh/vmagents_ed25519
DOMAIN=debian13         # libvirt domain
LIBVIRT_URI=qemu:///system
DIR=~/work              # where the agent starts on the VM (created if missing)
SESSION=claude          # tmux session; empty = no tmux
OS=linux                # or windows; detected from the SSH banner on first use
AGENT=claude            # or codex, gemini, opencode, aider
AGENTS=claude,codex     # installed on the VM
PORTS=3000,5173         # forwarded to this computer while connected
PROJECT=~/code/app      # the git repository sent with "vmagents project"
AUTOSTOP=on             # off: the VM keeps running after you leave
AUTOSNAP=3              # automatic snapshots to keep; 0 = none
IDLE=30                 # what "vmagents idle" set up on the VM (0 = off)
NOTIFY=on               # desktop notifications
CLIPBOARD=on            # copies on the VM land in this computer's clipboard
```

Environment: `VMAGENTS_CONFIG_DIR` (another config folder),
`VMAGENTS_BOOT_TIMEOUT` (seconds to wait for the VM, default 180),
`VMAGENTS_STOP_TIMEOUT` (seconds to wait for a shutdown, default 120).

<details>
<summary><b>How it works</b></summary>

- `ssh -l USER -p PORT -i KEY -o HostKeyAlias=vmagents-NAME`. The host key is
  stored under the profile name in vmagents's own `known_hosts`, so a VM whose
  DHCP address changes keeps its identity. The first connection accepts the
  key; after that a changed key is refused until `vmagents forget NAME` (for
  example after reinstalling the VM).
- On the VM a short POSIX `sh` script adds `~/.local/bin` to `PATH`, goes to
  `DIR` and runs `tmux new-session -A -s claude claude ...`. Arguments are
  quoted for `sh`, so the user's login shell (bash, zsh, fish) does not matter.
- Booting libvirt VMs: `virsh start`, then `virsh domifaddr`, then wait for the
  `SSH-2.0` banner. NAT forwards (passt, slirp, VirtualBox) accept connections
  before sshd is up, so an open port alone is not enough.
- vmagents does not change the VM's sshd settings. Once key login works, you
  may want to turn off password login (`PasswordAuthentication no`).

</details>

## Tests

```sh
python3 -m unittest discover -s tests -t .
```

The tests run vmagents against fake `ssh`, `virsh`, `virt-install` and
`curl`; the scripts meant for the VM really run, under `sh`, in a throwaway
home directory. CI runs them on every push, with shellcheck.

<details>
<summary>What the automatic tests cover</summary>

- `test_cli.py`: the commands against fake `ssh` and `virsh`; the autostart
  hook in real interactive bash and zsh on a pseudo-terminal.
- `test_e2e.py`: the real OpenSSH client against a local SSH server
  (`asyncssh`): password then key login, host-key pinning, quoting through a
  real remote shell.
- `test_login.py`: the token reaches Claude however it is started and never
  appears on a command line.
- `test_mount.py`, `test_mcp.py`: `mount`/`umount` with a fake sshfs; MCP
  spoken to `vmagents mcp` the way Claude Code does, every tool.
- `test_create.py`: `create` and `delete` (which refuses VMs it did not make),
  the missing `default` pool, the UI under uv, and a Turkish locale (built
  with `localedef` when it is not installed).
- `test_windows.py`: OS detection, and the PowerShell commands sent, decoded.
- `test_stop.py`: autostop, `start`, `stop`; every reason to keep a VM on.
- `test_snapshots.py`: automatic snapshots and their pruning, names, labels, `undo`.
- `test_idle_notify.py`: `hook.sh` with Claude's hook input, the watcher, the idle installers.
- `test_extras.py`: `open` (a fake ssh that really listens), the clipboard,
  the agents, the Windows hooks.
- `test_projects.py`: a real git repository sent to the fake VM and back, with
  real git on both sides: commits, changed, new and ignored files, the refused
  re-send, `--discard`, only new commits sent later.
- `test_ui.py` (needs Textual and pyte, else skipped): the UI with Textual's
  test pilot against a fake `vmagents`: Vim keys, language, the new-VM form,
  snapshots, terminal tabs on a real pseudo-terminal, creating in a tab,
  projects and changes, the working/waiting marks. `test_ui_backend.py`: the
  `--json` output and options it builds on.

</details>

<details>
<summary>What was tried by hand, on real VMs</summary>

- `vmagents create` on libvirt 11.3 with all four images (Debian 13, Debian
  12, Ubuntu 24.04, Arch Linux): download, checksum, base volume, VM,
  cloud-init, Claude Code, doctor, shut down and start again, `delete`, `prune`.
- Inside the Arch VM: connect, detach and reattach, autostart on a plain
  `ssh` login, and the whole test suite. On a Debian 13 cloud image: setup,
  connect, autostart and skipping it with `LC_VMAGENTS=off`.
- Autostop (quit: off; `Ctrl-b d`, a second connection, an SSH login: stays
  on), idle shutdown after 1 minute, a snapshot at each start and `undo`, live
  snapshots, notifications; on Arch and on Windows 10.
- `vmagents open` with a web server on the VM; the clipboard with real tmux
  (Turkish letters too); Codex, Gemini CLI, aider and OpenCode installed and
  started, Codex's login page through port 1455.
- Claude Code hooks in Claude Code 2.1, and on Windows 10 under Git Bash, with
  the notification arriving here.
- `vmagents mcp`: a real `claude -p` session that wrote, ran, edited and
  re-ran a program in the Arch VM with only these tools; `mount` both ways.
- Windows 10 22H2: setup (key as administrator, Git via the fallback
  installer, Claude Code), doctor, connect, autostart, `shell`, and 13 hard
  arguments (quotes, trailing backslash, `%PATH%`, `&|<>^`, Turkish) byte for byte.
- The UI in a real terminal: a VM made from the form, resized and deleted;
  shells and Claude Code in tabs (tmux's line drawing included), Turkish,
  snapshot names and labels on real libvirt.
- Projects on the Arch VM: git installed by `project`, an agent's commit and
  uncommitted files in `changes`, the refused re-send, `take`, merge, send
  again; in the UI the changes tab and a shell tab going from working to waiting.

</details>

## Limitations

- Only libvirt VMs are started, stopped and snapshotted. Other hypervisors
  (VirtualBox, VMware, Hyper-V, a cloud VM) work through `--host`: connect,
  open, clipboard, notifications, idle shutdown; start them yourself.
- Windows VMs have no tmux, so sessions end with the connection; skipping
  autostart with `LC_VMAGENTS=off` works on Linux VMs only.
- The clipboard, other agents and projects need a Linux VM.
- A plain `ssh` login never shuts the VM down (vmagents is not running then;
  the idle shutdown does, later). The idle shutdown cannot see long jobs that
  use little CPU (a download, a `sleep`).
- The UI tells "working" from "waiting" by the terminal's output only: a
  program busy without printing anything for a few seconds looks like it waits.
- Tested on Linux hosts. macOS needs bash 4+ (Homebrew) and `timeout` (coreutils).

## License

MIT. If vmagents saved you some setup time, a ⭐ on GitHub helps others find it.
