"""vmforai login: a token made on this computer reaches Claude on the VM,
however Claude is started there, without passing through command lines."""
import base64
import os
import re
import subprocess

from tests.helpers import SandboxTest, write_exe, VMFORAI
from tests.ptyrun import run_in_pty

TOKEN = "sk-ant-oat01-" + "A1b2_C3d4-" * 9
APIKEY = "sk-ant-api03-" + "Zz9" * 30

# A claude that reports what login it would use.
CLAUDE_ENV = '#!/bin/sh\necho "token=${CLAUDE_CODE_OAUTH_TOKEN-} key=${ANTHROPIC_API_KEY-} args=$*" >>"$STUB_REMOTE_LOG"\n'
# A tmux that runs the session's command right away, as tmux would.
TMUX_RUN = '''#!/bin/sh
echo "tmux $*" >>"$STUB_REMOTE_LOG"
shift; while [ $# -gt 0 ]; do case $1 in -A) shift ;; -s|-c) shift 2 ;; *) break ;; esac; done
exec "$@"
'''


class LoginTests(SandboxTest):
    def setUp(self):
        super().setUp()
        self.sb.run("add", "vm", "--host", "192.0.2.7", "--os", "linux", check=0)
        self.env = {"STUB_SSH_EXEC": "1"}
        self.file = self.sb.remote_home / ".config" / "vmforai" / "claude-env"

    def login(self, token, *args, check=0):
        return self.sb.run("login", "vm", *args, input=token + "\n", env=self.env, check=check)

    def test_token_is_stored_privately(self):
        r = self.login(TOKEN)
        self.assertIn("Logged in: Claude Code on 'vm' now uses this token.", r.stdout)
        self.assertEqual(self.file.read_text(), f"CLAUDE_CODE_OAUTH_TOKEN={TOKEN}\n")
        self.assertEqual(oct(self.file.stat().st_mode & 0o777), "0o600")
        # never on a command line
        for c in self.sb.calls("ssh"):
            self.assertNotIn(TOKEN, " ".join(c["argv"]))
        self.login(APIKEY)
        self.assertEqual(self.file.read_text(), f"ANTHROPIC_API_KEY={APIKEY}\n")
        self.assertIn("Removed", self.sb.run("login", "vm", "--remove", env=self.env, check=0).stdout)
        self.assertFalse(self.file.exists())

    def test_rejects_other_text(self):
        for bad in ("", "hello", "sk-ant-short", "sk-ant-oat01-$(touch x)aaaaaaaaaaaaaaaaaaaaaa"):
            with self.subTest(bad=bad):
                r = self.login(bad, check=1)
                self.assertIn("not a Claude token", r.stderr)
        self.assertFalse(self.file.exists())

    def test_token_taken_from_setup_token(self):
        # The real flow: in a terminal, "claude setup-token" runs here and prints the token.
        write_exe(self.sb.bin / "claude", "#!/bin/sh\n"
                  f"printf 'Long-lived authentication token created successfully!\\n\\nYour OAuth token (valid for 1 year):\\n\\n"
                  f"\\033[1m{TOKEN}\\033[22m\\n\\nStore this token securely.\\n'\n")
        out = run_in_pty([str(VMFORAI), "login", "vm"], dict(self.sb.env, **self.env), str(self.sb.tmp))
        self.assertIn("Logged in", out)
        self.assertEqual(self.file.read_text(), f"CLAUDE_CODE_OAUTH_TOKEN={TOKEN}\n")

    def test_paste_when_not_found(self):
        write_exe(self.sb.bin / "claude", "#!/bin/sh\necho 'cancelled'\n")
        out = run_in_pty([str(VMFORAI), "login", "vm"], dict(self.sb.env, **self.env), str(self.sb.tmp),
                         answers=[("Token: ", TOKEN + "\r")])
        self.assertNotIn(TOKEN, out)  # hidden input
        self.assertEqual(self.file.read_text(), f"CLAUDE_CODE_OAUTH_TOKEN={TOKEN}\n")

    def test_claude_gets_the_token(self):
        self.login(TOKEN)
        self.sb.remote_tool("claude", CLAUDE_ENV)
        self.sb.remote_tool("tmux", TMUX_RUN)
        self.sb.run("vm", "--continue", env=self.env, check=0)
        self.sb.run("vm", "--no-tmux", env=self.env, check=0)
        calls = self.sb.remote_calls()
        self.assertTrue(calls[0].startswith("tmux new-session -A -s claude -c"), calls[0])
        self.assertNotIn(TOKEN, calls[0])  # not in tmux's command line either
        hooks = f"--settings {self.sb.remote_home}/.config/vmforai/claude-settings.json"
        self.assertEqual(calls[1], f"token={TOKEN} key= args={hooks} --continue")
        self.assertEqual(calls[2], f"token={TOKEN} key= args={hooks}")

    def test_no_token_no_change(self):
        self.sb.remote_tool("claude", CLAUDE_ENV)
        self.sb.run("vm", "--no-tmux", env=self.env, check=0)
        hooks = f"--settings {self.sb.remote_home}/.config/vmforai/claude-settings.json"
        self.assertEqual(self.sb.remote_calls(), [f"token= key= args={hooks}"])

    def test_shells_and_autostart_get_it(self):
        self.login(TOKEN)
        batch = self.sb.tmp / "batch"
        batch.write_text("0")
        self.sb.run("setup", "vm", "--no-install", env=dict(self.env, STUB_SSH_BATCH_RC=str(batch)), check=0)
        rc = self.sb.remote_home / ".bashrc"
        r = subprocess.run(["bash", "-c", f". {rc}; echo $CLAUDE_CODE_OAUTH_TOKEN"], capture_output=True, text=True,
                           env={"HOME": str(self.sb.remote_home), "PATH": "/usr/bin:/bin"}, stdin=subprocess.DEVNULL)
        self.assertEqual(r.stdout, TOKEN + "\n")
        # autostart, through tmux
        self.sb.remote_tool("claude", CLAUDE_ENV)
        self.sb.remote_tool("tmux", TMUX_RUN)
        rc.write_text(rc.read_text() + "PS1='READY''> '\n")
        env = {"HOME": str(self.sb.remote_home), "PATH": str(self.sb.remote_bin), "SSH_CONNECTION": "1 2 3 4",
               "TERM": "dumb", "STUB_REMOTE_LOG": str(self.sb.remote_log)}
        run_in_pty(["bash", "-i"], env, str(self.sb.remote_home), answers=[("READY> ", "exit\n")])
        self.assertIn(f"token={TOKEN} key= args=", self.sb.remote_calls())

    def test_doctor_reports_login(self):
        from tests.helpers import listening_port
        srv, port = listening_port()
        self.addCleanup(srv.close)
        self.sb.run("add", "vm", "--host", "127.0.0.1", "--port", str(port), check=0)
        (self.sb.home / ".ssh").mkdir()
        (self.sb.home / ".ssh" / "vmforai_ed25519").write_text("x")
        batch = self.sb.tmp / "batch"
        batch.write_text("0")
        env = dict(self.env, STUB_SSH_BATCH_RC=str(batch))
        self.assertIn("info  Claude login: not yet (run: vmforai login vm)", self.sb.run("doctor", "vm", env=env).stdout)
        self.login(TOKEN)
        self.assertIn('ok    Claude login: token from "vmforai login"', self.sb.run("doctor", "vm", env=env).stdout)

    def test_windows(self):
        self.sb.run("add", "vm", "--os", "windows", check=0)
        self.sb.run("login", "vm", input=TOKEN + "\n", check=0)
        call = self.sb.calls("ssh")[-1]
        self.assertEqual(call["stdin"], f"CLAUDE_CODE_OAUTH_TOKEN={TOKEN}\n")
        script = base64.b64decode(re.search(r"-EncodedCommand (\S+)$", call["argv"][-1]).group(1)).decode("utf-16-le")
        self.assertIn('[IO.File]::WriteAllText($f, [Console]::In.ReadToEnd())', script)
        self.assertNotIn(TOKEN, call["argv"][-1])
        # and connect loads it before starting claude.exe
        self.sb.run("vm", check=0)
        enc = re.search(r"-EncodedCommand (\S+)$", self.sb.calls("ssh")[-1]["argv"][-1]).group(1)
        self.assertIn('Set-Item "env:$($Matches[1])" $Matches[2]', base64.b64decode(enc).decode("utf-16-le"))
