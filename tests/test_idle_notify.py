"""Idle shutdown (vmforai idle), Claude's hooks on the VM and desktop
notifications (the watcher). The VM side really runs where it can: hook.sh
and the watcher's poll script, in the fake VM home. The idle service itself
was tried on the Arch and Windows 10 VMs (they powered off after 1 and 2
idle minutes, and stayed on during SSH sessions)."""
import json
import os
import subprocess
import sys
import time

from tests.helpers import ROOT, SandboxTest, write_exe
from tests.test_stop import Base
from tests.test_windows import decode


def var(name):
    """A variable of the vmforai script, as the script defines it."""
    return subprocess.run(["bash", "-c", f'source <(sed "/^main \\"\\$@\\"; exit$/d" "$0"); printf "%s" "${name}"',
                           str(ROOT / "vmforai")], capture_output=True, text=True, check=True).stdout


class HookTests(SandboxTest):
    def setUp(self):
        super().setUp()
        self.d = self.sb.remote_home / ".config" / "vmforai"
        self.d.mkdir(parents=True)
        self.hook = self.d / "hook.sh"
        self.hook.write_text(var("HOOK_SH") + "\n")
        self.proj = self.sb.remote_home / "my project"
        self.proj.mkdir()

    def run_hook(self, arg, payload):
        subprocess.run(["sh", str(self.hook), arg], input=json.dumps(payload), text=True, check=True,
                       env={"HOME": str(self.sb.remote_home), "PATH": "/usr/bin:/bin"}, cwd=self.proj)

    def test_state(self):
        self.run_hook("busy", {"hook_event_name": "UserPromptSubmit", "prompt": "x" * 100000})
        self.assertEqual((self.d / "claude-state").read_text(), "busy\n")
        self.run_hook("idle", {"hook_event_name": "Stop"})
        self.assertEqual((self.d / "claude-state").read_text(), "idle\n")
        self.assertFalse((self.d / "events").exists())

    def test_notify(self):
        self.run_hook("notify", {"session_id": "s", "message": "Claude needs your permission to use Bash",
                                 "hook_event_name": "Notification"})
        self.run_hook("notify", {"hook_event_name": "Notification"})
        lines = (self.d / "events").read_text().splitlines()
        self.assertRegex(lines[0], r"^\d{13}\tmy project\tClaude needs your permission to use Bash$")
        self.assertTrue(lines[1].endswith("\tmy project\tClaude is waiting for you"))
        self.assertEqual((self.d / "claude-state").read_text(), "idle\n")

    def test_events_file_stays_small(self):
        (self.d / "events").write_text("".join(f"{i}\tp\tm\n" for i in range(200)))
        self.run_hook("notify", {"message": "last"})
        lines = (self.d / "events").read_text().splitlines()
        self.assertEqual(len(lines), 100)
        self.assertTrue(lines[-1].endswith("\tlast"))

    def test_settings(self):
        settings = json.loads(var("CLAUDE_SETTINGS"))
        hooks = settings["hooks"]
        self.assertEqual(set(hooks), {"UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "Notification"})
        self.assertEqual(hooks["Stop"][0]["hooks"][0]["command"], 'sh "$HOME/.config/vmforai/hook.sh" idle')
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "*")
        self.assertEqual(hooks["Notification"][0]["hooks"][0]["command"].split()[-1], "notify")

    def test_connect_installs_the_hooks_once(self):
        self.hook.unlink()
        self.sb.run("add", "vm", "--host", "192.0.2.7", "--os", "linux", "--no-tmux", check=0)
        self.sb.remote_tool("claude")
        self.sb.run("vm", env={"STUB_SSH_EXEC": "1"}, check=0)
        self.assertEqual(self.hook.read_text(), var("HOOK_SH") + "\n")
        settings = self.d / "claude-settings.json"
        self.assertEqual(json.loads(settings.read_text()), json.loads(var("CLAUDE_SETTINGS")))
        before = settings.stat().st_mtime_ns
        time.sleep(0.05)
        self.sb.run("vm", env={"STUB_SSH_EXEC": "1"}, check=0)
        self.assertEqual(settings.stat().st_mtime_ns, before)  # unchanged: not rewritten


class IdleTests(Base):
    def test_linux(self):
        self.sb.run("idle", "vm", "30", check=0)
        self.assertIn("IDLE=30\n", self.profile())
        argv = self.sb.calls("ssh")[-1]["argv"]
        script = argv[-1]
        self.assertIn("/etc/systemd/system/vmforai-idle.service", script)
        self.assertIn("ExecStart=/bin/sh /usr/local/libexec/vmforai-idle $m", script)
        self.assertIn("vmforai '30' '#!/bin/sh", script)  # minutes, then the idle script
        self.assertIn("systemctl poweroff", script)
        self.sb.run("idle", "vm", "off", check=0)
        self.assertIn("IDLE=0\n", self.profile())
        self.assertIn("vmforai '0' '#!/bin/sh", self.sb.calls("ssh")[-1]["argv"][-1])
        self.assertEqual(self.sb.run("idle", "vm", "soon").returncode, 2)

    def test_install_script_needs_systemd_and_sudo(self):
        # Runs the installer on the fake VM, which has neither.
        self.sb.run("add", "vm", "--host", "127.0.0.1", check=0)
        r = self.sb.run("idle", "vm", "30", env={"STUB_SSH_EXEC": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"idle shutdown needs (root or sudo|systemd) on the VM")
        self.assertNotIn("IDLE=", self.profile())

    def test_windows(self):
        self.sb.run("add", "vm", "--os", "windows", check=0)
        self.sb.run("idle", "vm", "45", check=0)
        _, ps = decode(self.sb.calls("ssh")[-1]["argv"][-1])
        self.assertIn("$m = 45", ps)
        self.assertIn("Register-ScheduledTask -TaskName vmforai-idle", ps)
        self.assertIn("-ExecutionTimeLimit ([TimeSpan]::Zero)", ps)
        self.assertIn('-UserId "SYSTEM"', ps)
        self.assertIn("Stop-Computer -Force", ps)
        self.assertIn("TotalSeconds -gt $Step * 5", ps)  # time jumps (fast startup) start the count again

    def test_idle_script_is_valid_sh(self):
        for name in ("IDLE_LOOP_SH", "IDLE_INSTALL_SH", "WATCH_SH", "HOOK_SH"):
            with self.subTest(name=name):
                subprocess.run(["sh", "-n"], input=var(name), text=True, check=True)

    def test_create_option(self):
        r = self.sb.run("create", "x", "--idle", "soon", "--no-setup")
        self.assertEqual(r.returncode, 1)
        self.assertIn("--idle takes minutes, or off", r.stderr)


PGREP = """#!/bin/sh
# claude processes: one per line of $HOME/claude-counts, then 0
f=$HOME/claude-counts
n=$(head -n 1 "$f" 2>/dev/null); sed -i 1d "$f" 2>/dev/null
echo "${n:-0}"
"""


class WatcherTests(Base):
    def setUp(self):
        super().setUp()
        self.notified = self.sb.tmp / "notified"
        write_exe(self.sb.bin / "notify-send",
                  f'#!/bin/sh\nprintf "%s|" "$@" >>{self.notified}\necho >>{self.notified}\n')
        self.sb.remote_tool("pgrep", PGREP)
        self.events = self.sb.remote_home / ".config" / "vmforai" / "events"
        self.events.parent.mkdir(parents=True)

    def watch(self, counts, env=None, timeout=20):
        (self.sb.remote_home / "claude-counts").write_text("".join(f"{c}\n" for c in counts))
        e = {"STUB_SSH_EXEC": "1", "VMFORAI_WATCH_INTERVAL": "0.2", "XDG_RUNTIME_DIR": str(self.sb.tmp)}
        e.update(env or {})
        return self.sb.run("__watch", "vm", env=e, timeout=timeout, check=0)

    def test_new_events_become_notifications(self):
        # Old events are not shown again; one appears while the watcher runs.
        self.events.write_text("1000\tproj\told news\n")
        # Added during the first poll, which only notes the VM's clock.
        later = r"9999999999999\tmy app\tClaude needs your permission to use Bash\n"
        self.sb.remote_tool("pgrep", PGREP + f'[ -f "$HOME/added" ] || {{ touch "$HOME/added"; printf "{later}" >>"{self.events}"; }}\n')
        self.watch([1, 1, 1, 0, 0])
        lines = self.notified.read_text().splitlines()
        self.assertEqual(lines, ["-a|vmforai|Claude Code (vm)|my app: Claude needs your permission to use Bash|"])
        polls = [c for c in self.sb.calls("ssh") if "vmforai-watch" in c["argv"][-1]]
        self.assertEqual(len(polls), 5)  # stops after Claude is gone twice
        self.assertIn("BatchMode=yes", polls[0]["argv"])

    def test_stops_when_the_vm_is_off(self):
        self.sb.set_vm("shut off")
        self.watch([1])
        self.assertEqual(self.sb.calls("ssh"), [])
        self.assertNotIn("start", self.virsh_cmds())  # never starts the VM

    def test_one_watcher_per_vm(self):
        import fcntl
        lock = open(self.sb.tmp / f"vmforai-watch-{os.getuid()}-vm.lock", "a")
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.watch([1, 0, 0])
        self.assertEqual(self.sb.calls("ssh"), [])

    def test_ssh_failures_end_it(self):
        r = self.watch([], env={"STUB_SSH_EXEC": "", "STUB_SSH_RC": "255"}, timeout=30)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(self.sb.calls("ssh")), 20)

    def test_unexpected_answers_end_it(self):
        r = self.watch([], env={"STUB_SSH_EXEC": "", "STUB_SSH_OUTPUT": ""}, timeout=30)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(self.sb.calls("ssh")), 20)

    def connect_with_display(self, **env):
        e = {"DISPLAY": ":9", "VMFORAI_WATCH_INTERVAL": "0.2", "XDG_RUNTIME_DIR": str(self.sb.tmp),
             "STUB_SSH_OUTPUT": "claude=0\n"}
        e.update(env)
        self.sb.run("vm", "--keep", env=e, check=0)
        deadline = time.time() + 10
        while time.time() < deadline:
            polls = [c for c in self.sb.calls("ssh") if "vmforai-watch" in c["argv"][-1]]
            if len(polls) >= 2:
                break
            time.sleep(0.1)
        time.sleep(0.5)
        return polls

    def test_connect_starts_it(self):
        self.assertEqual(len(self.connect_with_display()), 2)

    def test_not_without_a_desktop_or_when_off(self):
        self.assertEqual(self.connect_with_display(DISPLAY=""), [])
        self.sb.run("notify", "vm", "off", check=0)
        self.assertIn("NOTIFY=off\n", self.profile())
        self.assertEqual(self.connect_with_display(), [])
        self.assertIn("Notifications are on", self.sb.run("notify", "vm", "on", check=0).stdout)

    def test_does_not_keep_the_vm_on(self):
        other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)",
                                  "-oHostKeyAlias=vmforai-vm", "sh -c ': vmforai-watch'"])
        self.addCleanup(other.wait)
        self.addCleanup(other.kill)
        r = self.sb.run("vm", check=0)
        self.assertIn("VM testvm is off.", r.stderr)
