"""vmagents was called vmclaude before 0.11. Settings, host keys, the SSH
key, files on the VMs, libvirt VMs and base images made under the old name,
and the old command name keep working."""
import json
import os
import subprocess

from tests.helpers import VMAGENTS, SandboxTest
from tests.test_create import IMAGE, CreateBase
from tests.test_stop import Base

KEY = "AAAAC3NzaC1lZDI1NTE5AAAAIGq0ZbW1cT8l0b8hY8m1oYb7o0p8bL4bQyS1vC3aZ2kX"


class HostTests(SandboxTest):
    def old(self):
        return self.sb.home / ".config" / "vmclaude"

    def make_old_setup(self):
        hosts = self.old() / "hosts"
        hosts.mkdir(parents=True)
        (hosts / "vm.conf").write_text("HOST=192.0.2.7\nUSER=dev\n")
        (hosts / "h2.conf").write_text("HOST=192.0.2.8\n")
        kh = self.old() / "known_hosts"
        # h2's entry hashed, as with HashKnownHosts yes
        kh.write_text(f"vmclaude-h2 ssh-ed25519 {KEY}2\n")
        subprocess.run(["ssh-keygen", "-H", "-f", str(kh)], capture_output=True, check=True)
        os.remove(str(kh) + ".old")
        with open(kh, "a") as f:
            f.write(f"vmclaude-vm ssh-ed25519 {KEY}\n")
        images = self.sb.home / ".cache" / "vmclaude" / "images"
        images.mkdir(parents=True)
        (images / "debian.qcow2").write_text("x")

    def test_settings_move_once(self):
        self.make_old_setup()
        r = self.sb.run("list", check=0)
        self.assertIn("vmclaude is now called vmagents: moved its settings to", r.stderr)
        self.assertIn("vm", r.stdout)
        self.assertFalse(self.old().exists())
        kh = (self.sb.conf / "known_hosts").read_text()
        self.assertIn(f"vmagents-vm ssh-ed25519 {KEY}\n", kh)
        self.assertIn(f"vmagents-h2 ssh-ed25519 {KEY}2\n", kh)
        self.assertTrue((self.sb.home / ".cache" / "vmagents" / "images" / "debian.qcow2").exists())
        self.assertEqual(self.sb.run("list", check=0).stderr, "")  # once

    def test_old_key_stays_in_use(self):
        ssh = self.sb.home / ".ssh"
        ssh.mkdir()
        (ssh / "vmclaude_ed25519").write_text("old key")
        self.sb.run("add", "vm", "--host", "192.0.2.7", "--os", "linux", check=0)
        self.sb.run("vm", check=0)
        argv = self.sb.calls("ssh")[0]["argv"]
        self.assertEqual(argv[argv.index("-i") + 1], str(ssh / "vmclaude_ed25519"))
        self.assertIn("HostKeyAlias=vmagents-vm", argv)

    def test_old_command_name(self):
        old = self.sb.bin / "vmclaude"
        old.symlink_to(VMAGENTS)
        r = subprocess.run([str(old), "--version"], capture_output=True, text=True, env=self.sb.env)
        self.assertTrue(r.stdout.startswith("vmagents "), r.stdout)

    def test_old_environment_variables(self):
        other = self.sb.tmp / "elsewhere"
        self.sb.run("add", "vm", "--host", "192.0.2.7", env={"VMCLAUDE_CONFIG_DIR": str(other)}, check=0)
        self.assertTrue((other / "hosts" / "vm.conf").exists())


class VMFilesTests(Base):
    def test_files_on_the_vm_move_once(self):
        self.sb.run("add", "h", "--host", "127.0.0.1", "--port", str(self.port), "--os", "linux", "--no-tmux", check=0)
        old = self.sb.remote_home / ".config" / "vmclaude"
        old.mkdir(parents=True)
        (old / "claude-env").write_text("CLAUDE_CODE_OAUTH_TOKEN=sk-ant-x\n")
        self.sb.remote_tool("claude")
        self.sb.run("h", env={"STUB_SSH_EXEC": "1"}, check=0)
        new = self.sb.remote_home / ".config" / "vmagents"
        self.assertEqual((new / "claude-env").read_text(), "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-x\n")
        self.assertTrue(old.is_symlink())  # old hooks and autostart lines still find their files
        self.assertTrue((old / "hook.sh").exists())

    def test_autostart_replaces_the_old_block(self):
        self.sb.run("add", "h", "--host", "127.0.0.1", "--port", str(self.port), "--os", "linux", check=0)
        rc = self.sb.remote_home / ".bashrc"
        rc.write_text("alias ll='ls -l'\n# >>> vmclaude autostart >>>\nold line\n# <<< vmclaude autostart <<<\n")
        self.sb.run("autostart", "h", "on", env={"STUB_SSH_EXEC": "1"}, check=0)
        text = rc.read_text()
        self.assertNotIn("vmclaude autostart", text)
        self.assertNotIn("old line", text)
        self.assertIn("# >>> vmagents autostart >>>", text)
        self.assertTrue(text.startswith("alias ll='ls -l'\n"))

    def test_old_idle_service_is_replaced(self):
        self.sb.run("idle", "vm", "30", check=0)
        script = self.sb.calls("ssh")[-1]["argv"][-1]
        self.assertIn("systemctl disable --now vmclaude-idle.service", script)
        self.assertIn("/etc/systemd/system/vmagents-idle.service", script)

    def test_the_watcher_is_known_by_both_names(self):
        from tests.test_idle_notify import var
        self.assertTrue(var("WATCH_SH").startswith(": vmagents-watch vmclaude-watch\n"))


class LibvirtTests(CreateBase):
    def test_old_base_image_is_reused(self):
        import hashlib
        old = f"vmclaude-base-debian13-{hashlib.sha512(IMAGE).hexdigest()[:12]}.qcow2"
        self.lv.write_text(json.dumps({"domains": {}, "volumes": {old: {"size": "1", "backing": None}}}))
        r = self.sb.run("create", "box", "--no-setup", check=0)
        self.assertIn(f"Using base volume {old}", r.stderr)
        self.assertEqual(self.state()["volumes"]["box.qcow2"]["backing"], old)

    def test_old_vm_can_be_deleted(self):
        self.lv.write_text(json.dumps({"domains": {"old": {"desc": "created by vmclaude", "state": "shut off"}},
                                       "volumes": {"old.qcow2": {}}}))
        (self.sb.conf / "hosts").mkdir(parents=True)
        (self.sb.conf / "hosts" / "old.conf").write_text("DOMAIN=old\nCREATED=1\n")
        self.sb.run("delete", "old", "--yes", check=0)
        self.assertNotIn("old", self.state()["domains"])


class WindowsTests(Base):
    def test_files_on_windows_move_once(self):
        from tests.test_windows import decode
        self.sb.run("add", "vm", "--os", "windows", check=0)
        self.sb.run("vm", "--keep", check=0)
        hooks = decode(self.sb.calls("ssh")[0]["argv"][-1])[1]
        self.assertIn('Join-Path $env:USERPROFILE ".config\\vmclaude"', hooks)
        self.assertIn("Move-Item -LiteralPath $o -Destination $n", hooks)
        self.assertIn("New-Item -ItemType Junction -Path $o -Target $n", hooks)
        self.assertLess(hooks.index("Move-Item"), hooks.index('"hook.sh"'))
