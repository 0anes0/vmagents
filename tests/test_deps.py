"""deps: what vmforai uses on this computer, installed with its package
manager. Against fake apt-get, dnf, pacman, zypper, apk, sudo, systemctl and
usermod, on a PATH without the real tools."""
import shutil
from pathlib import Path

from tests.helpers import VMFORAI, SandboxTest, write_exe
from tests.ptyrun import run_in_pty

RECORD = '#!/bin/sh\necho "$(basename "$0") $*" >>"$LOG"\n'
GONE = {"virsh", "virt-install", "qemu-img", "xorriso", "genisoimage", "mkisofs", "dnsmasq", "libvirtd", "virtqemud",
        "uv", "notify-send", "xclip", "xsel", "wl-copy", "sshfs", "git", "apt-get", "dnf", "pacman", "zypper", "apk",
        "sudo", "doas", "systemctl", "usermod", "getent", "rc-service", "python3", "curl"}


class DepsTests(SandboxTest):
    def setUp(self):
        super().setUp()
        hide = self.sb.tmp / "hide"
        hide.mkdir()
        for d in ("/usr/local/bin", "/usr/bin", "/bin"):
            for f in Path(d).iterdir() if Path(d).is_dir() else ():
                if f.name not in GONE and not f.name.startswith("python3") and not (hide / f.name).exists():
                    (hide / f.name).symlink_to(f)
        self.log = self.sb.tmp / "calls"
        self.sb.env.update(PATH=f"{self.sb.bin}:{hide}", LOG=str(self.log), VMFORAI_SBIN=str(self.sb.tmp / "sbin"),
                           DISPLAY="")
        write_exe(self.sb.bin / "sudo", '#!/bin/sh\necho "sudo $*" >>"$LOG"\nexec "$@"\n')
        write_exe(self.sb.bin / "systemctl", RECORD + '[ "$1" = cat ] && [ "$2" = libvirtd.service ] && exit 0\n'
                  '[ "$1" = is-active ] && exit 3\nexit 0\n')
        write_exe(self.sb.bin / "getent", '#!/bin/sh\n[ "$2" = libvirt ] && echo "libvirt:x:120:"\n')
        write_exe(self.sb.bin / "usermod", RECORD)
        real_id = shutil.which("id")
        write_exe(self.sb.bin / "id", f'#!/bin/sh\n[ "$1" = -nG ] && {{ echo "me users"; exit 0; }}\nexec {real_id} "$@"\n')
        # curl: uv's installer, which puts uv in ~/.local/bin.
        write_exe(self.sb.bin / "curl", RECORD + 'echo \'mkdir -p "$HOME/.local/bin" && printf "#!/bin/sh\\n" '
                  '>"$HOME/.local/bin/uv" && chmod +x "$HOME/.local/bin/uv"\'\n')

    def calls(self):
        return self.log.read_text() if self.log.exists() else ""

    def test_check(self):
        r = self.sb.run("deps", "--check")
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout, r"  ok +ssh ")
        self.assertRegex(r.stdout, r"  missing +virt-install +creating VMs")
        self.assertRegex(r.stdout, r"  missing +git ")
        self.assertNotIn("sshfs", r.stdout)  # only with --all
        self.assertNotIn("notify-send", r.stdout)  # no desktop
        self.assertIn("sshfs", self.sb.run("deps", "--check", "--all").stdout)
        self.assertNotIn("virt-install", self.sb.run("deps", "--check", "--no-libvirt").stdout)
        self.assertEqual(self.calls().count("install"), 0)  # --check installs nothing

    def test_debian(self):
        write_exe(self.sb.bin / "apt-get", RECORD)
        r = self.sb.run("deps", "--yes")
        self.assertIn("To install with apt (sudo asks for your password): python3 git libvirt-daemon-system "
                      "libvirt-clients virtinst qemu-system-x86 qemu-utils xorriso dnsmasq-base", r.stdout)
        calls = self.calls()
        self.assertIn("sudo apt-get -o DPkg::Lock::Timeout=600 update -qq", calls)
        self.assertIn("apt-get -o DPkg::Lock::Timeout=600 install -y python3 git libvirt-daemon-system libvirt-clients virtinst qemu-system-x86 "
                      "qemu-utils xorriso dnsmasq-base\n", calls)
        self.assertIn("curl -LsSf https://astral.sh/uv/install.sh", calls)
        self.assertTrue((self.sb.home / ".local" / "bin" / "uv").exists())
        self.assertIn("systemctl enable --now libvirtd.service", calls)
        self.assertRegex(calls, r"usermod -aG libvirt \S+\n")
        self.assertIn("Log out and in again", r.stdout)
        self.assertIn("still missing", r.stderr)  # the fake apt-get installs nothing

    def test_other_distributions(self):
        want = {
            "dnf": "dnf install -y python3 git libvirt-daemon-kvm libvirt-client virt-install qemu-kvm qemu-img "
                   "xorriso dnsmasq",
            "pacman": "pacman -S --needed --noconfirm python git libvirt virt-install qemu-desktop libisoburn dnsmasq",
            "zypper": "zypper --non-interactive install python3 git libvirt-daemon-qemu libvirt-daemon-driver-network "
                      "libvirt-client virt-install qemu-x86 qemu-tools xorriso dnsmasq",
            "apk": "apk add python3 git libvirt-daemon libvirt-client virt-install qemu-system-x86_64 qemu-img xorriso "
                   "dnsmasq",
        }
        for manager, line in want.items():
            with self.subTest(manager):
                for m in want:
                    (self.sb.bin / m).unlink(missing_ok=True)
                write_exe(self.sb.bin / manager, RECORD)
                self.log.write_text("")
                self.sb.run("deps", "--yes")
                self.assertIn(line + "\n", self.calls())

    def test_desktop_and_all(self):
        write_exe(self.sb.bin / "apt-get", RECORD)
        self.sb.run("deps", "--yes", "--all", "--no-libvirt")
        line = [l for l in self.calls().splitlines() if l.startswith("apt-get -o DPkg::Lock::Timeout=600 install")][0]
        self.assertTrue(line.endswith("python3 git libnotify-bin xclip sshfs"), line)
        self.assertNotIn("systemctl", self.calls())  # no libvirt: its service left alone

    def test_waits_for_apt(self):
        # apt busy at first (a computer updating itself just after it started): tried again.
        write_exe(self.sb.bin / "apt-get", RECORD + 'f="$LOG.busy"; [ "$3" = update ] && [ ! -e "$f" ] && '
                  '{ : >"$f"; echo "E: Could not get lock" >&2; exit 100; }\nexit 0\n')
        write_exe(self.sb.bin / "sleep", "#!/bin/sh\n")
        r = self.sb.run("deps", "--yes")
        self.assertIn("apt is busy", r.stderr)
        self.assertEqual(self.calls().count("update -qq"), 4)  # (sudo and apt-get, twice)
        self.assertIn("install -y", self.calls())

    def test_asks_first(self):
        write_exe(self.sb.bin / "apt-get", RECORD)
        r = self.sb.run("deps")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not going on without --yes", r.stderr)
        self.assertNotIn("install", self.calls())

    def test_no_package_manager(self):
        r = self.sb.run("deps", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no package manager here that vmforai knows", r.stderr)

    def test_first_run(self):
        # The first time vmforai runs in a terminal, what is missing comes by itself; once.
        write_exe(self.sb.bin / "apt-get", RECORD)
        env = dict(self.sb.env)
        env.pop("VMFORAI_NO_DEPS")
        out = run_in_pty([str(VMFORAI), "list"], env, self.sb.tmp)
        self.assertRegex(out, r"First run: vmforai puts what it uses on this computer:.* git ")
        self.assertIn("apt-get -o DPkg::Lock::Timeout=600 install -y", self.calls())
        self.assertTrue((self.sb.conf / "deps-checked").exists())
        self.log.write_text("")
        out = run_in_pty([str(VMFORAI), "list"], env, self.sb.tmp)
        self.assertNotIn("First run", out)
        self.assertEqual(self.calls(), "")
        # Not in a terminal (scripts, the UI's calls): never.
        (self.sb.conf / "deps-checked").unlink()
        self.assertNotIn("First run", self.sb.run("list", env={"VMFORAI_NO_DEPS": ""}).stdout)

    def test_help(self):
        self.assertIn("vmforai deps [--check]", self.sb.run("help", "deps", check=0).stdout)
        self.assertIn("install.ps1", self.sb.run("help", "deps", check=0).stdout)
