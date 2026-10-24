"""vmforai was called vmagents (0.11 to 0.24) and vmclaude before that.
Settings, host keys, the SSH key, files on the VMs, libvirt VMs and base
images made under the old names, and the old command names keep working."""
import json
import os
import subprocess

from tests.helpers import VMFORAI, SandboxTest
from tests.test_create import IMAGE, CreateBase
from tests.test_stop import Base

KEY = "AAAAC3NzaC1lZDI1NTE5AAAAIGq0ZbW1cT8l0b8hY8m1oYb7o0p8bL4bQyS1vC3aZ2kX"
OLD_NAMES = ("vmagents", "vmclaude")


class HostTests(SandboxTest):
    def make_old_setup(self, old_name):
        old = self.sb.home / ".config" / old_name
        hosts = old / "hosts"
        hosts.mkdir(parents=True)
        (hosts / "vm.conf").write_text("HOST=192.0.2.7\nUSER=dev\n")
        (hosts / "h2.conf").write_text("HOST=192.0.2.8\n")
        kh = old / "known_hosts"
        # h2's entry hashed, as with HashKnownHosts yes
        kh.write_text(f"{old_name}-h2 ssh-ed25519 {KEY}2\n")
        subprocess.run(["ssh-keygen", "-H", "-f", str(kh)], capture_output=True, check=True)
        os.remove(str(kh) + ".old")
        with open(kh, "a") as f:
            f.write(f"{old_name}-vm ssh-ed25519 {KEY}\n")
        images = self.sb.home / ".cache" / old_name / "images"
        images.mkdir(parents=True)
        (images / "debian.qcow2").write_text("x")
        return old

    def test_settings_move_once(self):
        for old_name in OLD_NAMES:
            with self.subTest(old_name):
                for d in (".config", ".cache"):
                    for n in ("vmforai",) + OLD_NAMES:
                        p = self.sb.home / d / n
                        if p.is_symlink():
                            p.unlink()
                        elif p.exists():
                            subprocess.run(["rm", "-rf", str(p)], check=True)
                old = self.make_old_setup(old_name)
                r = self.sb.run("list", check=0)
                self.assertIn(f"{old_name} is now called vmforai (short: vmf): its settings moved to", r.stderr)
                self.assertIn("vm", r.stdout)
                self.assertTrue(old.is_symlink())  # what still looks there finds them
                self.assertEqual(os.readlink(old), "vmforai")
                kh = (self.sb.conf / "known_hosts").read_text()
                self.assertIn(f"vmforai-vm ssh-ed25519 {KEY}\n", kh)
                self.assertIn(f"vmforai-h2 ssh-ed25519 {KEY}2\n", kh)
                self.assertTrue((self.sb.home / ".cache" / "vmforai" / "images" / "debian.qcow2").exists())
                self.assertTrue((self.sb.home / ".cache" / old_name).is_symlink())
                self.assertEqual(self.sb.run("list", check=0).stderr, "")  # once

    def test_old_key_stays_in_use(self):
        for old_name in OLD_NAMES:
            with self.subTest(old_name):
                ssh = self.sb.home / ".ssh"
                ssh.mkdir(exist_ok=True)
                for n in OLD_NAMES:
                    (ssh / f"{n}_ed25519").unlink(missing_ok=True)
                (ssh / f"{old_name}_ed25519").write_text("old key")
                self.sb.run("add", "vm", "--host", "192.0.2.7", "--os", "linux", check=0)
                self.sb.clear_log()
                self.sb.run("vm", check=0)
                argv = self.sb.calls("ssh")[0]["argv"]
                self.assertEqual(argv[argv.index("-i") + 1], str(ssh / f"{old_name}_ed25519"))
                self.assertIn("HostKeyAlias=vmforai-vm", argv)
                self.sb.run("rm", "vm", check=0)

    def test_old_command_names(self):
        for old_name in OLD_NAMES + ("vmf",):
            old = self.sb.bin / old_name
            old.symlink_to(VMFORAI)
            r = subprocess.run([str(old), "--version"], capture_output=True, text=True, env=self.sb.env)
            self.assertTrue(r.stdout.startswith("vmforai "), r.stdout)

    def test_updated_under_the_old_name(self):
        # "vmagents update" of 0.23 or 0.24 puts the new script in place of the old one: the
        # new names appear next to it, and the old one becomes a link.
        bin_ = self.sb.tmp / "inst"
        bin_.mkdir()
        old = bin_ / "vmagents"
        old.write_bytes(VMFORAI.read_bytes())
        old.chmod(0o755)
        r = subprocess.run([str(old), "--version"], capture_output=True, text=True, env=self.sb.env)
        self.assertTrue(r.stdout.startswith("vmforai "), r.stdout)
        self.assertIn("vmagents is now called vmforai; vmf is short for it.", r.stderr)
        self.assertEqual((bin_ / "vmforai").read_bytes(), VMFORAI.read_bytes())
        self.assertEqual(os.readlink(old), "vmforai")
        self.assertEqual(os.readlink(bin_ / "vmf"), "vmforai")
        r = subprocess.run([str(old), "--version"], capture_output=True, text=True, env=self.sb.env)
        self.assertEqual(r.stderr, "")  # once

    def test_old_environment_variables(self):
        for old_name in OLD_NAMES:
            with self.subTest(old_name):
                other = self.sb.tmp / f"elsewhere-{old_name}"
                self.sb.run("add", "vm", "--host", "192.0.2.7", env={f"{old_name.upper()}_CONFIG_DIR": str(other)},
                            check=0)
                self.assertTrue((other / "hosts" / "vm.conf").exists())


class VMFilesTests(Base):
    def test_files_on_the_vm_move_once(self):
        self.sb.run("add", "h", "--host", "127.0.0.1", "--port", str(self.port), "--os", "linux", "--no-tmux", check=0)
        self.sb.remote_tool("claude")
        for old_name in OLD_NAMES:
            with self.subTest(old_name):
                for n in ("vmforai",) + OLD_NAMES:
                    p = self.sb.remote_home / ".config" / n
                    if p.is_symlink():
                        p.unlink()
                    elif p.exists():
                        subprocess.run(["rm", "-rf", str(p)], check=True)
                old = self.sb.remote_home / ".config" / old_name
                old.mkdir(parents=True)
                (old / "claude-env").write_text("CLAUDE_CODE_OAUTH_TOKEN=sk-ant-x\n")
                self.sb.run("h", env={"STUB_SSH_EXEC": "1"}, check=0)
                new = self.sb.remote_home / ".config" / "vmforai"
                self.assertEqual((new / "claude-env").read_text(), "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-x\n")
                self.assertTrue(old.is_symlink())  # old hooks and autostart lines still find their files
                self.assertTrue((old / "hook.sh").exists())

    def test_autostart_replaces_the_old_blocks(self):
        self.sb.run("add", "h", "--host", "127.0.0.1", "--port", str(self.port), "--os", "linux", check=0)
        rc = self.sb.remote_home / ".bashrc"
        rc.write_text("alias ll='ls -l'\n# >>> vmclaude autostart >>>\nold line\n# <<< vmclaude autostart <<<\n"
                      "# >>> vmagents autostart >>>\nolder line\n# <<< vmagents autostart <<<\n")
        self.sb.run("autostart", "h", "on", env={"STUB_SSH_EXEC": "1"}, check=0)
        text = rc.read_text()
        self.assertNotIn("vmclaude autostart", text)
        self.assertNotIn("vmagents autostart", text)
        self.assertNotIn("old line", text)
        self.assertIn("# >>> vmforai autostart >>>", text)
        self.assertTrue(text.startswith("alias ll='ls -l'\n"))
        hook = (self.sb.remote_home / ".config" / "vmforai" / "autostart.sh").read_text()
        for switch in ("VMFORAI_NO_AUTOSTART", "VMAGENTS_NO_AUTOSTART", "LC_VMFORAI", "LC_VMAGENTS"):
            self.assertIn(switch, hook)  # what the old names' hosts send still skips it

    def test_old_idle_services_are_replaced(self):
        self.sb.run("idle", "vm", "30", check=0)
        script = self.sb.calls("ssh")[-1]["argv"][-1]
        self.assertIn("for o_ in vmagents vmclaude; do", script)
        self.assertIn("systemctl disable --now $o_-idle.service", script)
        self.assertIn("/etc/systemd/system/vmforai-idle.service", script)

    def test_the_watcher_is_known_by_all_names(self):
        from tests.test_idle_notify import var
        self.assertTrue(var("WATCH_SH").startswith(": vmforai-watch vmagents-watch vmclaude-watch\n"))


class LibvirtTests(CreateBase):
    def test_old_base_images_are_reused(self):
        import hashlib
        for old_name in OLD_NAMES:
            with self.subTest(old_name):
                old = f"{old_name}-base-debian13-{hashlib.sha512(IMAGE).hexdigest()[:12]}.qcow2"
                self.lv.write_text(json.dumps({"domains": {}, "volumes": {old: {"size": "1", "backing": None}}}))
                (self.sb.conf / "hosts" / "box.conf").unlink(missing_ok=True)
                r = self.sb.run("create", "box", "--no-setup", check=0)
                self.assertIn(f"Using base volume {old}", r.stderr)
                self.assertEqual(self.state()["volumes"]["box.qcow2"]["backing"], old)

    def test_old_vms_can_be_deleted(self):
        for old_name in OLD_NAMES:
            with self.subTest(old_name):
                self.lv.write_text(json.dumps({"domains": {"old": {"desc": f"created by {old_name}", "state": "shut off"}},
                                               "volumes": {"old.qcow2": {}}}))
                (self.sb.conf / "hosts").mkdir(parents=True, exist_ok=True)
                (self.sb.conf / "hosts" / "old.conf").write_text("DOMAIN=old\nCREATED=1\n")
                self.sb.run("delete", "old", "--yes", check=0)
                self.assertNotIn("old", self.state()["domains"])


class WindowsTests(Base):
    def test_files_on_windows_move_once(self):
        from tests.test_windows import decode
        self.sb.run("add", "vm", "--os", "windows", check=0)
        self.sb.run("vm", "--keep", check=0)
        hooks = decode(self.sb.calls("ssh")[0]["argv"][-1])[1]
        self.assertIn('foreach ($name in "vmagents", "vmclaude")', hooks)
        self.assertIn('Join-Path $env:USERPROFILE ".config\\$name"', hooks)
        self.assertIn("Move-Item -LiteralPath $o -Destination $n", hooks)
        self.assertIn("New-Item -ItemType Junction -Path $o -Target $n", hooks)
        self.assertLess(hooks.index("Move-Item"), hooks.index('"hook.sh"'))
