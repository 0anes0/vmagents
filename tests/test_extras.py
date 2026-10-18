"""vmagents open (port forwarding), the clipboard bridge, other agents than
Claude (codex, gemini, aider) and notifications from Windows VMs. Against the
fake ssh, virsh and VM; the real thing was tried on the Arch and Windows 10
VMs (a web server on the VM opened here, Claude's copies in tmux pasted here,
Codex, Gemini CLI and aider installed and started, a notification from Claude
on Windows)."""
import base64
import json
import socket
import subprocess
import time

from tests.helpers import ROOT, VMAGENTS, SandboxTest, write_exe
from tests.ptyrun import run_in_pty
from tests.test_idle_notify import var
from tests.test_stop import Base
from tests.test_windows import decode


def busy_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    return s, s.getsockname()[1]


def free_pair():
    """A port P where P and P+1 are free here."""
    for _ in range(50):
        a, p = busy_port()
        a.close()
        try:
            b = socket.socket()
            b.bind(("127.0.0.1", p + 1))
            b.close()
            return p
        except OSError:
            continue
    raise RuntimeError("no free port pair")


class OpenTests(Base):
    def open(self, *args, answers=None, **env):
        e = dict(self.sb.env, **env)
        return run_in_pty([str(VMAGENTS), "open", *args], e, str(self.sb.tmp),
                          answers=answers if answers is not None else [("Stop with Ctrl-C.", "\x03")])

    def fetch(self, port):
        with socket.create_connection(("127.0.0.1", port), timeout=5) as c:
            return c.recv(100).decode()

    def test_forwards_until_ctrl_c(self):
        port = free_pair()
        write_exe(self.sb.bin / "xdg-open", f'#!/bin/sh\necho "$@" >>{self.sb.tmp}/opened\n')
        seen = []

        def fetch_then_stop():  # while vmagents forwards
            seen.append(self.fetch(port))
            return "\x03"
        out = self.open("vm", str(port), answers=[("Stop with Ctrl-C.", fetch_then_stop)])
        self.assertIn(f"Port {port} of vm: http://localhost:{port}", out)
        self.assertEqual(seen, ["hello from the VM\n"])
        fwd = [c for c in self.sb.calls("ssh") if "-N" in c["argv"]][0]["argv"]
        self.assertIn(f"127.0.0.1:{port}:localhost:{port}", fwd)
        self.assertIn("ExitOnForwardFailure=yes", fwd)
        self.assertEqual((self.sb.tmp / "opened").read_text(), f"http://localhost:{port}\n")
        self.assertIn("VM testvm is off.", out)  # autostop afterwards
        self.assertEqual(self.state(), "shut off")

    def test_taken_port_moves_up(self):
        held, port = busy_port()
        self.addCleanup(held.close)
        out = self.open("vm", str(port), "--no-browser", "--keep")
        self.assertIn(f"Port {port} of vm: http://localhost:{port + 1} (port {port} is taken here)", out)
        self.assertEqual(self.state(), "running")

    def test_local_port(self):
        port = free_pair()
        out = self.open("vm", f"{port}:3000", "--no-browser", "--keep")
        self.assertIn(f"Port 3000 of vm: http://localhost:{port}", out)
        held, taken = busy_port()
        self.addCleanup(held.close)
        r = self.sb.run("open", "vm", f"{taken}:3000")
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"port {taken} is already in use on this computer", r.stderr)

    def test_default_vm_and_errors(self):
        self.assertEqual(self.sb.run("open", "vm").returncode, 2)
        self.assertIn("invalid port: 70000", self.sb.run("open", "vm", "70000").stderr)
        self.assertIn("no VM profile named 'nope'", self.sb.run("open", "nope", "3000").stderr)
        self.assertIn("not a port: x", self.sb.run("open", "vm", "x").stderr)
        port = free_pair()
        out = self.open(str(port), "--no-browser", "--keep")  # the only VM
        self.assertIn(f"Port {port} of vm", out)

    def test_forward_fails(self):
        r = self.sb.run("open", "vm", str(free_pair()), "--no-browser", env={"STUB_SSH_FORWARD_RC": "255"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("could not forward the port (SSH exit code 255)", r.stderr)


def fake_tmux(buffers):
    """A tmux whose newest paste buffer is the file `buffers`: name|content."""
    return f"""#!/bin/sh
f={buffers}
case $1 in
  list-buffers) [ -s "$f" ] && echo "$(cut -d'|' -f1 "$f") 1 5" ;;
  show-buffer) cut -d'|' -f2- "$f" | tr '~' '\\n' | head -c -1 ;;
esac
"""


class ClipboardTests(Base):
    def test_clip_script_prints_new_buffers(self):
        buffers = self.sb.tmp / "buffers"
        buffers.write_text("buffer0|old\n")
        write_exe(self.sb.remote_bin / "tmux", fake_tmux(buffers))
        for tool in ("base64", "head"):
            if not (self.sb.remote_bin / tool).exists():
                (self.sb.remote_bin / tool).symlink_to(subprocess.run(["sh", "-c", f"command -v {tool}"],
                                                                      capture_output=True, text=True).stdout.strip())
        p = subprocess.Popen(["sh", "-c", var("CLIP_SH")], stdout=subprocess.PIPE,
                             env={"PATH": str(self.sb.remote_bin)})
        time.sleep(1.2)
        buffers.write_text("buffer1|copied by Claude: ü~line 2\n")
        lines = []
        deadline = time.time() + 5
        while time.time() < deadline and not any(lines):
            lines.append(p.stdout.readline().decode().strip())
        self.assertEqual([base64.b64decode(x).decode() for x in lines if x], ["copied by Claude: ü\nline 2"])
        p.stdout.close()  # the connection is gone: the script ends by itself
        self.assertIsNotNone(p.wait(timeout=5))

    def copy(self, text):
        f = self.sb.tmp / "clipboard"
        write_exe(self.sb.bin / "xclip", f'#!/bin/sh\necho "$*" >>{f}.args\ncat >>{f}\necho "<end>" >>{f}\n')
        subprocess.run(["bash", "-c", f'source <(sed "/^main \\"\\$@\\"; exit$/d" "{ROOT}/vmagents"); clip_copy'],
                       input=text, text=True, check=True,
                       env={"PATH": f"{self.sb.bin}:/usr/bin:/bin", "DISPLAY": ":9", "HOME": str(self.sb.home)})
        return f.read_text() if f.exists() else ""

    def test_copies_each_buffer_here(self):
        lines = "\n" + base64.b64encode("héllo\nworld".encode()).decode() + "\n\nnot base64!\n\r\n"
        self.assertEqual(self.copy(lines), "héllo\nworld<end>\n")
        self.assertIn("-selection clipboard", (self.sb.tmp / "clipboard.args").read_text())

    def connect(self, **env):
        write_exe(self.sb.bin / "xclip", "#!/bin/sh\ncat >/dev/null\n")
        e = {"DISPLAY": ":9", "STUB_SSH_OUTPUT": "", "STUB_SSH_SLEEP": "0.5"}  # time for the clipboard's ssh
        e.update(env)
        self.sb.run("vm", "--keep", env=e, check=0)
        return [c for c in self.sb.calls("ssh") if "tmux list-buffers" in c["argv"][-1]]

    def test_connect_runs_it(self):
        clip = self.connect()
        self.assertEqual(len(clip), 1)
        self.assertIn("BatchMode=yes", clip[0]["argv"])

    def test_not_when_off_or_without_tmux(self):
        self.assertEqual(self.connect(DISPLAY=""), [])
        self.sb.run("clipboard", "vm", "off", check=0)
        self.assertIn("CLIPBOARD=off\n", self.profile())
        self.assertEqual(self.connect(), [])
        self.assertIn("lands in this computer's clipboard", self.sb.run("clipboard", "vm", "on", check=0).stdout)
        self.sb.clear_log()
        self.sb.run("vm", "--keep", "--no-tmux", env={"DISPLAY": ":9"}, check=0)
        self.assertEqual([c for c in self.sb.calls("ssh") if "tmux list-buffers" in c["argv"][-1]], [])


class AgentTests(Base):
    def connect_args(self, *args, env=None):
        self.sb.clear_log()
        self.sb.run("vm", "--keep", *args, env=dict({"DISPLAY": ":9"}, **(env or {})), check=0)
        # The connection first; the clipboard's session runs alongside it.
        return sorted(self.sb.calls("ssh"), key=lambda c: "cd_dir" not in c["argv"][-1])

    def test_codex(self):
        calls = self.connect_args("--codex", "--full-auto")
        main = calls[0]["argv"]
        self.assertIn("127.0.0.1:1455:localhost:1455", main)  # its browser login
        self.assertTrue(main[-1].endswith(" '' 'codex' 'vm' 'codex' '--full-auto'"), main[-1])
        self.assertEqual([c for c in calls if "vmagents-watch" in c["argv"][-1]], [])  # no Claude hooks

    def test_session_names(self):
        self.assertTrue(self.connect_args("--gemini")[0]["argv"][-1].endswith(" '' 'gemini' 'vm' 'gemini'"))
        self.assertTrue(self.connect_args("--claude")[0]["argv"][-1].endswith(" '' 'claude' 'vm' 'claude'"))
        with open(self.sb.conf / "hosts" / "vm.conf", "a") as f:
            f.write("SESSION=work\n")
        cmd = self.connect_args("--aider")[0]["argv"][-1]
        self.assertTrue(cmd.endswith(" '' 'work-aider' 'vm' 'aider'"), cmd[-80:])

    def test_agent_command(self):
        self.assertEqual(self.sb.run("agent", "vm", check=0).stdout, "claude\n")
        r = self.sb.run("agent", "vm", "codex", env={"STUB_SSH_EXEC": "", "STUB_SSH_OUTPUT": "Installed codex\n"}, check=0)
        self.assertIn('"vmagents vm" opens codex now', r.stdout)
        self.assertIn("AGENT=codex\n", self.profile())
        self.assertIn("chatgpt.com/codex/install.sh", self.sb.calls("ssh")[-1]["argv"][-1])
        self.assertTrue(self.connect_args()[0]["argv"][-1].endswith(" '' 'codex' 'vm' 'codex'"))
        self.sb.run("agent", "vm", "claude", check=0)
        self.assertEqual(self.sb.run("agent", "vm", "copilot").returncode, 2)
        self.sb.run("add", "w", "--host", "192.0.2.4", "--os", "windows", check=0)
        self.assertIn("only Claude Code runs on Windows VMs", self.sb.run("agent", "w", "codex").stderr)
        (self.sb.conf / "hosts" / "w.conf").write_text("HOST=192.0.2.4\nAGENT=copilot\n")
        self.assertIn("invalid agent: copilot", self.sb.run("w").stderr)

    def test_installs_a_missing_agent_then_starts_it(self):
        # The fake VM has no codex; its "installer" (a fake curl) makes one.
        self.sb.run("add", "h", "--host", "127.0.0.1", "--port", str(self.port), "--os", "linux", check=0)
        self.sb.remote_tool("curl", "#!/bin/sh\necho 'mkdir -p \"$HOME/.local/bin\"; "
                                    "printf \"#!/bin/sh\\necho codex-cli 1.0 \\$*\\n\" >\"$HOME/.local/bin/codex\"; "
                                    "chmod +x \"$HOME/.local/bin/codex\"'\n")
        r = self.sb.run("h", "--codex", "--no-tmux", "hi", env={"STUB_SSH_EXEC": "1"}, check=0)
        self.assertIn("codex is not installed on the VM yet; installing it.", r.stderr)
        self.assertIn("Installed codex: codex-cli 1.0", r.stdout)
        self.assertTrue(r.stdout.rstrip().endswith("codex-cli 1.0 hi"), r.stdout)  # no --settings for codex

    def test_launcher_gives_settings_to_claude_only(self):
        d = self.sb.remote_home / ".config" / "vmagents"
        d.mkdir(parents=True)
        (d / "claude-settings.json").write_text("{}")
        (d / "codex-env").write_text("OPENAI_API_KEY=k1\n")
        for name in ("claude", "codex"):
            write_exe(self.sb.tmp / "b" / name, f'#!/bin/sh\necho {name} "$OPENAI_API_KEY" "$@"\n')
        run = lambda a: subprocess.run(["sh", "-c", var("CLAUDE_ENV_SH"), "x", str(d / f"{a}-env"),
                                        str(self.sb.tmp / "b" / a), "go"], capture_output=True, text=True).stdout
        self.assertEqual(run("claude"), f"claude  --settings {d}/claude-settings.json go\n")
        self.assertEqual(run("codex"), "codex k1 go\n")


class YoloTests(Base):
    connect_args = AgentTests.connect_args

    def test_yolo(self):
        self.assertEqual(self.sb.run("yolo", "vm", check=0).stdout, "off\n")
        self.assertTrue(self.connect_args()[0]["argv"][-1].endswith(" 'claude' 'vm' 'claude'"))
        cmd = self.connect_args("--yolo", "--continue")[0]["argv"][-1]  # once
        self.assertTrue(cmd.endswith(" 'claude' 'vm' 'claude' '--dangerously-skip-permissions' '--continue'"), cmd[-90:])
        self.assertIn("act without asking first", self.sb.run("yolo", "vm", "on", check=0).stdout)
        self.assertIn("YOLO=on\n", self.profile())
        self.assertTrue(json.loads(self.sb.run("list", "--json", check=0).stdout)[0]["yolo"])
        for agent, flag in (("codex", " '--dangerously-bypass-approvals-and-sandbox'"), ("gemini", " '--yolo'"),
                            ("aider", " '--yes-always'"), ("opencode", " '--auto'")):
            cmd = self.connect_args(f"--{agent}")[0]["argv"][-1]
            self.assertTrue(cmd.endswith(f" '{agent}' 'vm' '{agent}'{flag}"), (agent, cmd[-90:]))
        self.assertTrue(self.connect_args("--ask")[0]["argv"][-1].endswith(" 'claude' 'vm' 'claude'"))
        self.sb.run("yolo", "vm", "off", check=0)
        self.assertIn("YOLO=off\n", self.profile())
        self.assertEqual(self.sb.run("yolo", "vm", "maybe").returncode, 2)
        self.assertIn("vmagents yolo NAME", self.sb.run("help", "yolo", check=0).stdout)


class WindowsNotifyTests(Base):
    def setUp(self):
        super().setUp()
        self.sb.run("add", "vm", "--os", "windows", check=0)

    def scripts(self):
        return [decode(c["argv"][-1])[1] for c in self.sb.calls("ssh")]

    def test_hooks_installed_once(self):
        self.sb.run("vm", "--keep", check=0)
        first = self.scripts()
        self.assertIn('"hook.sh"', first[0])
        self.assertIn(var("HOOK_SH").splitlines()[-1], first[0])
        self.assertIn('--settings "', first[1])  # connect passes them to Claude
        self.sb.clear_log()
        self.sb.run("vm", "--keep", check=0)
        self.assertEqual(len(self.scripts()), 1)  # not again
        (self.sb.tmp / "virsh.state.snaps").write_text(json.dumps([["auto-1", "2026-10-16 09:00:00 +0300",
                                                                     "shutoff", ""]]))
        self.sb.run("undo", "vm", "--yes", check=0)
        self.sb.set_vm("running")
        self.sb.clear_log()
        self.sb.run("vm", "--keep", check=0)
        self.assertIn('"hook.sh"', self.scripts()[0])  # after undo, again

    def test_hooks_failure_is_only_a_warning(self):
        r = self.sb.run("vm", "--keep", env={"STUB_SSH_RC": "1"})
        self.assertIn("could not install Claude's hooks on the VM", r.stderr)
        self.assertIn("Invoke-Claude", self.scripts()[-1])

    def test_watcher(self):
        notified = self.sb.tmp / "notified"
        write_exe(self.sb.bin / "notify-send", f'#!/bin/sh\nprintf "%s|" "$@" >>{notified}\necho >>{notified}\n')
        # Windows answers with CRLF. Two polls with Claude, then two without.
        answers = self.sb.tmp / "answers"
        answers.write_text(json.dumps(["claude=1\r\nnow=1000\r\n",
                                       "claude=1\r\nnow=1500\r\n2000\twork\tClaude needs your input\r\n",
                                       "claude=0\r\nnow=1\r\n", "claude=0\r\nnow=1\r\n"]))
        write_exe(self.sb.bin / "ssh", f"""#!/usr/bin/env python3
import json, sys
open("{self.sb.log}", "a").write(json.dumps({{"prog": "ssh", "argv": sys.argv[1:]}}) + "\\n")
a = json.load(open("{answers}"))
sys.stdout.write(a.pop(0) if a else "claude=0\\n")
json.dump(a, open("{answers}", "w"))
""")
        self.sb.run("__watch", "vm", env={"VMAGENTS_WATCH_INTERVAL": "0.1", "XDG_RUNTIME_DIR": str(self.sb.tmp)},
                    timeout=20, check=0)
        self.assertEqual(notified.read_text().splitlines(),
                         ["-a|vmagents|Claude Code (vm)|work: Claude needs your input|"])
        polls = self.scripts()
        self.assertIn("# vmagents-watch", polls[0])
        self.assertIn("Get-Process claude", polls[0])
        self.assertIn("$last = ''", polls[0])
        self.assertIn("$last = '1000'", polls[1])
