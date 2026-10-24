"""Runs: a task for an agent on the VM, without a terminal (run), and the
list, logs, stop and clean-up (runs). The VM's scripts really run against a
fake tmux that starts the session's command in the background."""
import json
import os
import shutil
import time

from tests.helpers import write_exe
from tests.test_stop import Base

TMUX = r'''#!/usr/bin/env python3
import os, signal, subprocess, sys
a = sys.argv[1:]
d = os.path.join(os.environ["HOME"], ".tmux-sessions")
os.makedirs(d, exist_ok=True)
with open(os.path.join(os.environ["HOME"], ".tmux-log"), "a") as f:
    f.write(repr(a) + "\n")
def alive(n):
    try:
        os.kill(int(open(os.path.join(d, n)).read()), 0)
        return True
    except (OSError, ValueError):
        return False
if a[:1] == ["new-session"]:
    s = a[a.index("-s") + 1]
    cwd = a[a.index("-c") + 1]
    cmd = a[a.index("-c") + 2:]
    p = subprocess.Popen(cmd, cwd=cwd, start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    open(os.path.join(d, s), "w").write(str(p.pid))
elif a[:1] == ["kill-session"]:
    s = a[a.index("-t") + 1]
    try:
        os.killpg(int(open(os.path.join(d, s)).read()), signal.SIGTERM)
    except (OSError, ValueError):
        sys.exit(1)
elif a[:1] in (["list-sessions"], ["ls"]):
    names = [n for n in sorted(os.listdir(d)) if alive(n)]
    if not names:  # like tmux: no server, no sessions
        print("no server running", file=sys.stderr)
        sys.exit(1)
    print("\n".join(names))
'''

# Claude Code -p --output-format stream-json, as far as the formatter cares.
CLAUDE = r'''#!/bin/sh
echo "args: $*" >>"$HOME/agent-args"
echo '{"type":"system","subtype":"init"}'
echo '{"type":"assistant","message":{"content":[{"type":"text","text":"I will run the tests."}]}}'
sleep "${AGENT_SLEEP:-0}"
echo '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"npm test"}}]}}'
echo '{"type":"result","is_error":false,"num_turns":3,"duration_ms":4200,"total_cost_usd":0.12}'
exit "${AGENT_RC:-0}"
'''


class RunTests(Base):
    def setUp(self):
        super().setUp()
        for tool in ("mktemp", "pwd", "sort", "kill", "python3", "tail", "readlink"):
            if shutil.which(tool) and not (self.sb.remote_bin / tool).exists():
                (self.sb.remote_bin / tool).symlink_to(shutil.which(tool))
        write_exe(self.sb.remote_bin / "tmux", TMUX)
        write_exe(self.sb.remote_bin / "claude", CLAUDE)
        write_exe(self.sb.remote_bin / "codex", "#!/bin/sh\necho \"args: $*\" >>\"$HOME/agent-args\"\necho codex did it\n")
        self.sb.env.update(STUB_SSH_EXEC="1", DISPLAY="")
        self.runs = self.sb.remote_home / ".config" / "vmagents" / "runs"

    def wait_rc(self, i, seconds=10):
        f = self.runs / str(i) / "rc"
        for _ in range(seconds * 20):
            if f.exists():
                return f.read_text().strip()
            time.sleep(0.05)
        self.fail(f"run {i} did not end")

    def test_run_and_its_log(self):
        r = self.sb.run("run", "vm", "fix the failing tests", check=0)
        self.assertIn("Run 1 on vm: Claude Code works on it, without asking", r.stdout)
        self.assertIn("vmagents runs vm 1 -f", r.stdout)
        self.assertEqual(self.wait_rc(1), "0")
        self.assertEqual((self.runs / "1" / "task").read_text(), "fix the failing tests\n")
        args = (self.sb.remote_home / "agent-args").read_text()
        self.assertIn("-p --output-format stream-json --verbose --dangerously-skip-permissions fix the failing tests",
                      args)
        log = self.sb.run("runs", "vm", "1", check=0).stdout
        self.assertIn("I will run the tests.", log)
        self.assertIn("* Bash(npm test)", log)
        self.assertIn("-- finished: 3 turns, 4s, $0.12", log)
        self.assertIn("-- vmagents: the run ended, exit code 0", log)
        listing = self.sb.run("runs", "vm", check=0).stdout
        self.assertRegex(listing, r"\n1 +Claude Code +done +\d{4}-\d\d-\d\d \d\d:\d\d +fix the failing tests\n")
        data = json.loads(self.sb.run("runs", "vm", "--json", check=0).stdout)
        self.assertEqual((data[0]["id"], data[0]["agent"], data[0]["state"], data[0]["task"]),
                         (1, "claude", "0", "fix the failing tests"))
        self.assertIsInstance(data[0]["ended"], int)

    def test_wait_follows_it(self):
        r = self.sb.run("run", "vm", "--wait", "--", "add", "a", "--help", "flag", env={"AGENT_SLEEP": "1"}, check=0)
        self.assertIn("I will run the tests.", r.stdout)
        self.assertIn("* Bash(npm test)", r.stdout)
        self.assertIn("exit code 0", r.stdout)
        self.assertIn("add a --help flag", (self.sb.remote_home / "agent-args").read_text())
        r = self.sb.run("run", "vm", "--wait", "break it", env={"AGENT_RC": "3"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("exit code 3", r.stdout)
        self.assertRegex(self.sb.run("runs", "vm", check=0).stdout, r"\n2 +Claude Code +failed \(3\)")

    def test_other_agents_and_stdin(self):
        self.sb.run("run", "vm", "--codex", input="refactor the parser\nand keep the API\n", check=0)
        self.assertEqual(self.wait_rc(1), "0")
        args = (self.sb.remote_home / "agent-args").read_text()
        self.assertIn("exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox refactor the parser\n"
                      "and keep the API", args)
        self.assertIn("codex did it", self.sb.run("runs", "vm", "1", check=0).stdout)  # not reformatted
        self.assertIn("AGENTS=codex", self.profile())

    def test_stop_and_clean(self):
        self.sb.run("run", "vm", "a long one", env={"AGENT_SLEEP": "30"}, check=0)
        for _ in range(100):
            if (self.runs / "1" / "pid").exists():
                break
            time.sleep(0.05)
        self.assertRegex(self.sb.run("runs", "vm", check=0).stdout, r"\n1 +Claude Code +running ")
        self.assertIn("Run 1 on vm stopped.", self.sb.run("runs", "vm", "1", "--stop", check=0).stdout)
        self.assertEqual(self.wait_rc(1), "143")
        self.assertRegex(self.sb.run("runs", "vm", check=0).stdout, r"\n1 +Claude Code +stopped ")
        self.assertIn("Deleted 1 run(s)", self.sb.run("runs", "vm", "--clean", check=0).stdout)
        self.assertIn("No runs on vm yet", self.sb.run("runs", "vm", check=0).stdout)

    def test_notifies_when_it_ends(self):
        log = self.sb.tmp / "notified"
        write_exe(self.sb.bin / "notify-send", f'#!/bin/sh\necho "$@" >>"{log}"\n')
        r = self.sb.run("run", "vm", "ship it", env={"DISPLAY": ":9", "VMAGENTS_WATCH_INTERVAL": "0.2"}, check=0)
        self.assertIn("A notification comes when it ends.", r.stdout)
        for _ in range(200):
            if log.exists() and log.read_text():
                break
            time.sleep(0.05)
        self.assertIn("vm: task 1 done ship it", log.read_text())

    def test_notifies_the_phone(self):
        # No desktop here; notifications on the phone are on (ntfy): it waits for the end all the same.
        sent = self.sb.tmp / "ntfy"
        write_exe(self.sb.bin / "curl", f'#!/bin/sh\nprintf "%s\\n" "$*" >>"{sent}"\n')
        (self.sb.conf / "phone").mkdir(parents=True)
        (self.sb.conf / "phone" / "ntfy").write_text("SERVER=https://ntfy.example\nTOPIC=vmagents-abc\nTOKEN=\n")
        write_exe(self.sb.remote_bin / "claude", CLAUDE.replace('exit "${AGENT_RC:-0}"', "exit 2"))
        r = self.sb.run("run", "vm", "ship it", env={"VMAGENTS_WATCH_INTERVAL": "0.2"}, check=0)
        self.assertIn("A notification comes when it ends.", r.stdout)
        for _ in range(200):
            if sent.exists() and sent.read_text():
                break
            time.sleep(0.05)
        line = sent.read_text()
        body = json.loads(line[line.index("{"):line.rindex("}") + 1])
        self.assertEqual((body["topic"], body["title"], body["message"], body["tags"], body["priority"]),
                         ("vmagents-abc", "vm: task 1 failed (exit code 2)", "ship it", ["warning"], 4))
        self.assertTrue(line.rstrip().endswith("https://ntfy.example"))

    def test_problems(self):
        self.assertEqual(self.sb.run("run", "vm").returncode, 2)  # no task
        self.assertIn("give the task", self.sb.run("run", "vm", input="  \n").stderr)
        self.assertIn("unknown option --model", self.sb.run("run", "vm", "--model", "x").stderr)
        self.assertIn("no run 7 on vm", self.sb.run("runs", "vm", "7").stderr)
        self.sb.set_vm("shut off")
        self.assertIn("vm is off", self.sb.run("runs", "vm").stderr)
        self.assertEqual(self.sb.run("runs", "vm", "--json", check=0).stdout, "[]\n")
        for cmd in ("run", "runs"):
            self.assertIn(f"vmagents {cmd} NAME", self.sb.run("help", cmd, check=0).stdout)


class IdleSeesRunsTests(Base):
    def test_idle_loop_counts_a_run(self):
        from tests.test_idle_notify import var
        self.assertIn("/.config/vmagents/runs/*/pid", var("IDLE_LOOP_SH"))
        self.assertIn('echo "vmagents run"', var("IDLE_LOOP_SH"))
