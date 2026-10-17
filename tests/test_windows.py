"""Windows VMs, against the fake ssh: OS detection from the SSH banner, and
the PowerShell commands vmagents sends (decoded and checked). The scripts
themselves were run on a real Windows 10 VM; see the README."""
import base64
import gzip
import re
import subprocess
import unittest

from tests.helpers import ROOT, SandboxTest, listening_port

WIN_BANNER = b"SSH-2.0-OpenSSH_for_Windows_9.5\r\n"
ENCODED = re.compile(r"^powershell (-NoLogo -NoProfile[A-Za-z -]*) -ExecutionPolicy Bypass -EncodedCommand ([A-Za-z0-9+/=]+)$")


def decode(command):
    """powershell ... -EncodedCommand B64 -> (flags, script). Follows the
    gzip payload of win_run to the script it carries."""
    m = ENCODED.match(command)
    assert m, command
    script = base64.b64decode(m.group(2)).decode("utf-16-le")
    gz = re.search(r"FromBase64String\('([A-Za-z0-9+/=]+)'\)", script)
    if gz:
        script = gzip.decompress(base64.b64decode(gz.group(1))).decode()
    return m.group(1), script


def bash_fn(*args):
    """Call a vmagents function directly."""
    r = subprocess.run(["bash", "-c", 'source <(sed "/^main \\"\\$@\\"; exit$/d" "$0"); "$@"', str(ROOT / "vmagents"), *args],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


class DetectTests(SandboxTest):
    def detect(self, banner):
        srv, port = listening_port(banner=banner)
        self.addCleanup(srv.close)
        self.sb.run("add", "vm", "--host", "127.0.0.1", "--port", str(port), check=0)
        r = self.sb.run("vm", check=0)
        conf = (self.sb.conf / "hosts" / "vm.conf").read_text()
        return r, conf, self.sb.calls("ssh")[-1]["argv"][-1]  # after the hooks on Windows

    def test_windows_banner(self):
        r, conf, cmd = self.detect(WIN_BANNER)
        self.assertIn("OS=windows\n", conf)
        self.assertIn("Detected a Windows VM.", r.stderr)
        flags, _ = decode(cmd)
        self.assertEqual(flags, "-NoLogo -NoProfile")  # interactive: no -NonInteractive
        self.assertIn("(Windows)", self.sb.run("list", check=0).stdout)

    def test_linux_banner(self):
        _, conf, cmd = self.detect(b"SSH-2.0-OpenSSH_10.0p2 Debian-7\r\n")
        self.assertIn("OS=linux\n", conf)
        self.assertTrue(cmd.startswith("sh -c '"))

    def test_unreachable_is_not_saved(self):
        self.sb.run("add", "vm", "--host", "127.0.0.1", "--port", "1", check=0)
        self.sb.run("vm", check=0)
        self.assertNotIn("OS=", (self.sb.conf / "hosts" / "vm.conf").read_text())

    def test_bad_os_value(self):
        self.assertEqual(self.sb.run("add", "vm", "--host", "h", "--os", "macos").returncode, 1)


class CommandTests(SandboxTest):
    def setUp(self):
        super().setUp()
        self.sb.run("add", "w", "--host", "192.0.2.8", "--user", "emin", "--os", "windows", "--dir", "~/work", check=0)

    def last_command(self):
        return self.sb.calls("ssh")[-1]["argv"][-1]

    def test_connect_script(self):
        self.sb.run("w", "-p", "it's ‘curly’", check=0)
        flags, script = decode(self.last_command())
        self.assertIn("Resolve-Dir '~/work'", script)
        self.assertIn("@('-p', 'it''s ‘‘curly’’')", script)
        self.assertIn("exit (Invoke-Claude $c.Source $line $d)", script)
        self.assertIn("Run: vmagents setup w", script)
        self.assertIn("-T", self.sb.calls("ssh")[-1]["argv"])

    def test_too_many_arguments_fail_cleanly(self):
        r = self.sb.run("w", "--", *(["x" * 100] * 40))
        self.assertEqual(r.returncode, 1)
        self.assertIn("Windows command too long", r.stderr)

    def test_shell_skips_autostart(self):
        self.sb.run("shell", "w", check=0)
        flags, script = decode(self.last_command())
        self.assertIn("-NoExit", flags)
        self.assertIn('$env:VMAGENTS_NO_AUTOSTART = "1"', script)

    def test_setup(self):
        batch = self.sb.tmp / "batch"
        batch.write_text("1 0")
        r = self.sb.run("setup", "w", env={"STUB_SSH_BATCH_RC": str(batch)}, check=0)
        self.assertIn("Windows has no tmux", r.stdout)
        cmds = [c["argv"][-1] for c in self.sb.calls("ssh") if c["argv"][-1] != "exit 0"]
        self.assertEqual(len(cmds), 4)  # key, install, hook file, profile
        pub = (self.sb.home / ".ssh" / "vmagents_ed25519.pub").read_text().strip()
        _, addkey = decode(cmds[0])
        self.assertIn(f"$k = '{pub}'", addkey)
        self.assertIn("administrators_authorized_keys", addkey)
        self.assertIn('"*S-1-5-32-544:F"', addkey)
        _, install = decode(cmds[1])
        self.assertIn("curl.exe -fsSL", install)
        self.assertIn("Get-FileHash -Algorithm SHA256", install)
        self.assertIn("winget install --id Git.Git", install)
        _, hook = decode(cmds[2])
        self.assertIn("function Invoke-Claude", hook)
        self.assertIn("$vmagentsDir = ''~/work''", hook)  # a literal inside a literal
        _, profile = decode(cmds[3])
        self.assertIn("Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned", profile)
        for c in cmds:
            self.assertLess(len(c), 8000)

    def test_doctor(self):
        out = "claude=2.1.300 (Claude Code)\r\ngit=git version 2.56.0.windows.2\r\nhook=on\r\n"
        srv, port = listening_port(banner=WIN_BANNER)
        self.addCleanup(srv.close)
        self.sb.run("add", "w", "--host", "127.0.0.1", "--port", str(port), check=0)
        (self.sb.home / ".ssh").mkdir()
        (self.sb.home / ".ssh" / "vmagents_ed25519").write_text("x")
        batch = self.sb.tmp / "batch"
        batch.write_text("0")
        r = self.sb.run("doctor", "w", env={"STUB_SSH_BATCH_RC": str(batch), "STUB_SSH_OUTPUT": out}, check=0)
        self.assertIn("(SSH-2.0-OpenSSH_for_Windows_9.5)", r.stdout)
        self.assertIn("ok    Claude Code on the VM: 2.1.300 (Claude Code)", r.stdout)
        self.assertIn("ok    Git for Windows: git version 2.56.0.windows.2", r.stdout)
        self.assertNotIn("tmux", r.stdout)


class QuotingTests(unittest.TestCase):
    def test_psq(self):
        self.assertEqual(bash_fn("psq", "it's"), "'it''s'")
        self.assertEqual(bash_fn("psq", "‘a’ ‚b‛"), "'‘‘a’’ ‚‚b‛‛'")
        self.assertEqual(bash_fn("psq", '$x "y" `z`'), "'$x \"y\" `z`'")

    def test_ps_array(self):
        self.assertEqual(bash_fn("ps_array"), "@()")
        self.assertEqual(bash_fn("ps_array", "a", "", "b c"), "@('a', '', 'b c')")


if __name__ == "__main__":
    unittest.main()
