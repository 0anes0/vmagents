# vmagents on a Windows 10 or 11 computer: it runs in WSL (Ubuntu), and a
# "vmagents" command here starts it there.
# Usage, in PowerShell:
#   irm https://raw.githubusercontent.com/emincan2000/vmagents/main/install.ps1 | iex
# or, from a clone: powershell -ExecutionPolicy Bypass -File install.ps1 [-Distro Ubuntu] [-Force] [-Uninstall]
param([string]$Distro = "Ubuntu", [switch]$Uninstall, [switch]$Force)

$ErrorActionPreference = "Stop"
$env:WSL_UTF8 = "1"  # wsl.exe writes UTF-8 then, not UTF-16
$Bin = Join-Path $env:LOCALAPPDATA "vmagents"
$Raw = "https://raw.githubusercontent.com/emincan2000/vmagents/main"

function Say($s) { Write-Host $s }
function Fail($s) { throw "vmagents: $s" }

# The user's PATH, with or without the folder of the "vmagents" command.
function Set-UserPath([bool]$add) {
  $p = [Environment]::GetEnvironmentVariable("Path", "User")
  $parts = @(($p -split ";") | Where-Object { $_ -and $_ -ne $Bin })
  if ($add) { $parts += $Bin }
  [Environment]::SetEnvironmentVariable("Path", ($parts -join ";"), "User")
}

# (In a function: with "irm | iex", exit would close the PowerShell window.)
function Install-VmAgents {
  if ($Uninstall) {
    Remove-Item -Recurse -Force $Bin -ErrorAction SilentlyContinue
    Set-UserPath $false
    Say "Removed the vmagents command here. In WSL, ~/.local/bin/vmagents is still there"
    Say "(remove it with: wsl -d $Distro -- bash -c 'rm ~/.local/bin/vmagents')."
    return
  }

  # 1. WSL. Installing it needs an administrator and a restart.
  & wsl.exe --status *> $null
  if ($LASTEXITCODE -ne 0) {
    # In a virtual machine, WSL 2's hypervisor needs nested virtualization, and
    # without it Windows may hang at its logo on the next start (seen in a KVM VM).
    $cs = Get-CimInstance Win32_ComputerSystem
    if (-not $Force -and "$($cs.Manufacturer) $($cs.Model)" -match "QEMU|KVM|VMware|VirtualBox|innotek|Virtual Machine|Xen|Parallels|Bochs") {
      Fail ("this Windows runs in a virtual machine ($($cs.Manufacturer) $($cs.Model)). WSL 2 needs nested virtualization " +
        "there, and without it Windows may not start again. Install vmagents on the computer that runs the VMs instead; " +
        "or take a snapshot of this VM first and run this with -Force.")
    }
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
      [Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) { Fail "WSL is not installed. Run this again in PowerShell as administrator: it installs WSL." }
    Say "Installing WSL and $Distro (a restart follows)..."
    & wsl.exe --install -d $Distro
    Say ""
    Say "Restart Windows, open $Distro from the Start menu once (it asks for a user name and"
    Say "password), then run this installer again."
    return
  }

  # 2. The Linux distribution, set up once by hand (its user and password).
  $list = (& wsl.exe -l -q) -join "`n" -replace "`0", ""
  if (-not ($list -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -eq $Distro })) {
    Say "Installing $Distro in WSL..."
    & wsl.exe --install -d $Distro
    Say ""
    Say "Open $Distro from the Start menu once (it asks for a user name and password), then run this"
    Say "installer again."
    return
  }

  # 3. vmagents in it, and what it needs (sudo asks for the password set in step 2).
  Say "Installing vmagents in $Distro..."
  & wsl.exe -d $Distro -e bash -lc "command -v curl >/dev/null || { sudo apt-get update -qq && sudo apt-get install -y curl; }; curl -fsSL $Raw/install.sh | bash"
  if ($LASTEXITCODE -ne 0) { Fail "installing vmagents in $Distro failed (see above)" }
  # Windows 10's WSL cannot run VMs itself (no nested virtualization): no libvirt
  # there. Windows 11's can; "vmagents deps" in WSL adds it.
  $build = [Environment]::OSVersion.Version.Build
  $extra = if ($build -ge 22000) { "" } else { " --no-libvirt" }
  & wsl.exe -d $Distro -e bash -lc "~/.local/bin/vmagents deps --yes$extra"
  if ($LASTEXITCODE -ne 0) { Say "Some of what vmagents uses is missing; later, in ${Distro}: vmagents deps" }

  # 4. "vmagents" here.
  New-Item -ItemType Directory -Force -Path $Bin | Out-Null
  # (-e: no shell of WSL's own in between, which would expand "$@" too early.)
  $cmd = "@echo off`r`nwsl.exe -d $Distro -e bash -lc ""exec ~/.local/bin/vmagents \""`$@\"""" vmagents %*`r`n"
  [IO.File]::WriteAllText((Join-Path $Bin "vmagents.cmd"), $cmd)
  Set-UserPath $true
  $env:Path = "$env:Path;$Bin"

  Say ""
  Say "vmagents is installed: a new terminal (PowerShell, cmd or Windows Terminal) has the vmagents command."
  if ($build -lt 22000) {
    Say "On Windows 10, WSL cannot run VMs itself. Use VMs from Hyper-V, VirtualBox or VMware (or another"
    Say "computer), with their address:   vmagents add dev --host 192.168.1.50 --user you"
  } else {
    Say "In WSL, libvirt makes VMs:   vmagents create dev"
  }
  Say "Next: vmagents   (it asks for your VM the first time)"
}

Install-VmAgents
