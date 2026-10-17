"""Shutting libvirt VMs down: autostop after connect/shell, the checks that
keep a VM in use running, and start/stop/autostop. Against the fake ssh and
virsh; the real thing was tried on an Arch and a Windows 10 VM."""
import subprocess
import sys

from tests.helpers import SandboxTest, listening_port
from tests.test_windows import decode

IDLE_STATES = ("running", "shut off")


class Base(SandboxTest):
    def setUp(self):
        super().setUp()
        self.listener, self.port = listening_port()
        self.addCleanup(self.listener.close)
        self.sb.run("add", "vm", "--domain", "testvm", "--port", str(self.port), "--os", "linux", check=0)
        self.sb.set_vm("running")

    def virsh_cmds(self):
        return [c["argv"][2] for c in self.sb.calls("virsh")]

    def state(self):
        return self.sb.virsh_state.read_text().split("|")[0]

    def profile(self):
        return (self.sb.conf / "hosts" / "vm.conf").read_text()


class AutostopTests(Base):
    def test_connect_shuts_down_a_free_vm(self):
        r = self.sb.run("vm", check=0)
        self.assertIn("Shutting down VM testvm...", r.stderr)
        self.assertIn("VM testvm is off.", r.stderr)
        self.assertIn("shutdown", self.virsh_cmds())
        self.assertEqual(self.state(), "shut off")
        ssh = self.sb.calls("ssh")
        self.assertEqual(len(ssh), 2)  # Claude, then the check
        self.assertIn("BatchMode=yes", ssh[1]["argv"])
        self.assertIn("tmux list-sessions", ssh[1]["argv"][-1])

    def test_busy_vm_stays_on(self):
        out = "tmux on the VM still has session(s): claude\nlogged in on the VM: bob@pts/1\n"
        r = self.sb.run("vm", env={"STUB_SSH_OUTPUT": out}, check=0)
        self.assertIn("VM testvm stays on: tmux on the VM still has session(s): claude; "
                      "logged in on the VM: bob@pts/1.", r.stderr)
        self.assertIn("Back to Claude: vmagents vm", r.stderr)
        self.assertIn("Shut it down: vmagents stop vm", r.stderr)
        self.assertNotIn("shutdown", self.virsh_cmds())
        self.assertEqual(self.state(), "running")

    def test_keep(self):
        for args in (["vm", "--keep"], ["--keep", "vm"], ["connect", "--keep", "vm"]):
            with self.subTest(args=args):
                self.sb.clear_log()
                r = self.sb.run(*args, check=0)
                self.assertNotIn("shutdown", self.virsh_cmds())
                self.assertEqual(len(self.sb.calls("ssh")), 1)
                self.assertNotIn("--keep", self.sb.calls("ssh")[0]["argv"][-1])
                self.assertEqual(r.stderr, "")

    def test_autostop_off(self):
        r = self.sb.run("autostop", "vm", "off", check=0)
        self.assertIn("Autostop is off", r.stdout)
        self.assertIn("AUTOSTOP=off\n", self.profile())
        self.sb.run("vm", check=0)
        self.assertNotIn("shutdown", self.virsh_cmds())
        self.assertEqual(len(self.sb.calls("ssh")), 1)
        self.sb.run("autostop", "vm", "on", check=0)
        self.assertIn("AUTOSTOP=on\n", self.profile())
        self.sb.run("vm", check=0)
        self.assertIn("shutdown", self.virsh_cmds())

    def test_autostop_arguments(self):
        self.assertEqual(self.sb.run("autostop", "vm", "maybe").returncode, 2)
        self.assertEqual(self.sb.run("autostop", "vm").returncode, 2)
        self.sb.run("add", "h", "--host", "192.0.2.1", check=0)
        r = self.sb.run("autostop", "h", "on")
        self.assertEqual(r.returncode, 1)
        self.assertIn("needs a libvirt VM", r.stderr)
        with open(self.sb.conf / "hosts" / "vm.conf", "a") as f:
            f.write("AUTOSTOP=yes\n")
        r = self.sb.run("vm")
        self.assertEqual(r.returncode, 1)
        self.assertIn("invalid AUTOSTOP: yes (on or off)", r.stderr)

    def test_broken_connection_keeps_vm(self):
        r = self.sb.run("vm", env={"STUB_SSH_RC": "255"})
        self.assertEqual(r.returncode, 255)
        self.assertIn("SSH connection to", r.stderr)
        self.assertNotIn("shutdown", self.virsh_cmds())

    def test_claude_exit_code_is_kept(self):
        r = self.sb.run("vm", env={"STUB_SSH_RC": "3"})
        self.assertEqual(r.returncode, 3)
        self.assertIn("could not check the VM over SSH", r.stderr)  # the check got rc 3 too
        self.assertNotIn("shutdown", self.virsh_cmds())

    def test_other_connection_from_here_keeps_vm(self):
        # Any process with the profile's HostKeyAlias: vmagents shell, sshfs, ...
        other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", "-oHostKeyAlias=vmagents-vm"])
        self.addCleanup(other.wait)
        self.addCleanup(other.kill)
        r = self.sb.run("vm", check=0)
        self.assertIn("another connection from this computer is open", r.stderr)
        self.assertNotIn("Back to Claude", r.stderr)
        self.assertEqual(len(self.sb.calls("ssh")), 1)  # no need to ask the VM
        self.assertNotIn("shutdown", self.virsh_cmds())

    def test_similar_profile_name_does_not_count(self):
        other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", "-oHostKeyAlias=vmagents-vm2"])
        self.addCleanup(other.wait)
        self.addCleanup(other.kill)
        self.sb.run("vm", check=0)
        self.assertIn("shutdown", self.virsh_cmds())

    def test_shell(self):
        r = self.sb.run("shell", "vm", check=0)
        self.assertIn("VM testvm is off.", r.stderr)
        self.sb.set_vm("running")
        self.sb.clear_log()
        self.sb.run("shell", "--keep", "vm", check=0)
        self.assertNotIn("shutdown", self.virsh_cmds())
        self.sb.run("shell", "vm", "uptime", check=0)  # one command: VM stays on
        self.assertNotIn("shutdown", self.virsh_cmds())

    def test_plain_ssh_host_is_never_stopped(self):
        self.sb.run("add", "h", "--host", "127.0.0.1", "--port", str(self.port), "--os", "linux", check=0)
        self.sb.clear_log()
        r = self.sb.run("h", check=0)
        self.assertEqual(self.sb.calls("virsh"), [])
        self.assertEqual(len(self.sb.calls("ssh")), 1)
        self.assertEqual(r.stderr, "")

    def test_shutdown_that_hangs(self):
        r = self.sb.run("vm", env={"STUB_VIRSH_SHUTDOWN_IGNORED": "1", "VMAGENTS_STOP_TIMEOUT": "1"}, check=0)
        self.assertIn("VM testvm is still running after 1s. Pull the plug: vmagents stop vm --force", r.stderr)

    def test_windows_check(self):
        self.sb.run("add", "vm", "--os", "windows", check=0)
        self.sb.run("vm", check=0)
        scripts = [decode(c["argv"][-1])[1] for c in self.sb.calls("ssh")]
        self.assertIn("hook.sh", scripts[0])  # Claude's hooks, the first time
        self.assertIn("Invoke-Claude", scripts[1])
        script = scripts[2]
        self.assertIn("Win32_ComputerSystem", script)
        self.assertIn("Get-Process claude", script)
        self.assertIn("shutdown", self.virsh_cmds())


class BusyScriptTests(Base):
    """The Linux check really runs, on the fake VM, with fake tmux/who/pgrep."""

    def setUp(self):
        super().setUp()
        self.sb.remote_tool("claude")

    def run_vm(self, tmux="", who="", pgrep=1):
        self.sb.remote_tool("tmux", f'#!/bin/sh\n[ "$1" = list-sessions ] && printf "{tmux}"\nexit 0\n')
        self.sb.remote_tool("who", f'#!/bin/sh\nprintf "{who}"\n')
        self.sb.remote_tool("pgrep", f"#!/bin/sh\nexit {pgrep}\n")
        return self.sb.run("vm", env={"STUB_SSH_EXEC": "1"}, check=0)

    def test_free(self):
        r = self.run_vm()
        self.assertIn("VM testvm is off.", r.stderr)

    def test_tmux_sessions_and_logins(self):
        r = self.run_vm(tmux="claude\\nwork\\n",
                        who="emin pts/0 2026-10-16 19:06 (tmux(710).%%0)\\nbob pts/1 2026-10-16 19:07 (10.0.0.9)\\n",
                        pgrep=0)
        # tmux panes are not logins; Claude inside tmux is not reported twice
        self.assertIn("VM testvm stays on: tmux on the VM still has session(s): claude work; "
                      "logged in on the VM: bob@pts/1.\n", r.stderr)

    def test_claude_without_tmux(self):
        r = self.run_vm(pgrep=0)
        self.assertIn("VM testvm stays on: Claude Code still runs on the VM.", r.stderr)


class StopStartTests(Base):
    def test_stop(self):
        r = self.sb.run("stop", "vm", check=0)
        self.assertIn("VM testvm is off.", r.stderr)
        self.assertEqual(self.virsh_cmds(), ["domstate", "shutdown", "domstate"])
        r = self.sb.run("stop", "vm", check=0)
        self.assertIn("VM testvm is already off.", r.stderr)

    def test_stop_force(self):
        r = self.sb.run("stop", "vm", "--force", check=0)
        self.assertIn("VM testvm is off (forced).", r.stderr)
        self.assertIn("destroy", self.virsh_cmds())
        self.assertNotIn("shutdown", self.virsh_cmds())

    def test_stop_paused_vm_resumes_first(self):
        self.sb.set_vm("paused")
        self.sb.run("stop", "vm", check=0)
        cmds = self.virsh_cmds()
        self.assertLess(cmds.index("resume"), cmds.index("shutdown"))

    def test_stop_timeout_fails(self):
        r = self.sb.run("stop", "vm", env={"STUB_VIRSH_SHUTDOWN_IGNORED": "1", "VMAGENTS_STOP_TIMEOUT": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("still running after 1s", r.stderr)

    def test_stop_needs_libvirt(self):
        self.sb.run("add", "h", "--host", "192.0.2.1", check=0)
        r = self.sb.run("stop", "h")
        self.assertEqual(r.returncode, 1)
        self.assertIn("is not a libvirt VM", r.stderr)
        self.assertEqual(self.sb.run("stop", "vm", "--bogus").returncode, 2)

    def test_start(self):
        self.sb.set_vm("shut off")
        r = self.sb.run("start", "vm", check=0)
        self.assertIn("Starting VM testvm", r.stderr)
        self.assertRegex(r.stdout, r"^VM vm is running: \S+@127\.0\.0\.1\n$")
        self.assertEqual(self.sb.calls("ssh"), [])
        self.assertEqual(self.state(), "running")

    def test_connect_waits_for_a_shutdown_to_finish(self):
        self.sb.set_vm("in shutdown", polls=2)
        r = self.sb.run("vm", "--keep", check=0)
        self.assertIn("VM testvm is shutting down; waiting to start it again...", r.stderr)
        self.assertIn("start", self.virsh_cmds())
        self.assertEqual(len(self.sb.calls("ssh")), 1)

    def test_list_shows_state(self):
        self.assertIn("libvirt:testvm (running)", self.sb.run("list", check=0).stdout)
        self.sb.set_vm("shut off")
        self.assertIn("libvirt:testvm (shut off)", self.sb.run("list", check=0).stdout)
