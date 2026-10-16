"""End to end: the real OpenSSH client against a local SSH server (asyncssh)
that runs commands under /bin/sh in a fake VM home, like sshd does.

Needs the asyncssh package; skipped without it:
    uv run --no-project --with asyncssh python -m unittest tests.test_e2e
"""
import asyncio
import os
import shutil
import threading
import unittest
from pathlib import Path

from tests import stubs
from tests.helpers import Sandbox, write_exe
from tests.test_cli import WRAP

try:
    import asyncssh
except ImportError:  # pragma: no cover
    asyncssh = None

PASSWORD = "vm-password"


class FakeVM:
    """SSH server on 127.0.0.1. Accepts PASSWORD, or keys in the fake home's
    authorized_keys (read on every attempt, like sshd)."""

    def __init__(self, home: Path, path: str, log: Path, shell="/bin/sh"):
        self.home, self.path, self.log, self.shell = home, path, log, shell
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        if not self.ready.wait(20):
            raise RuntimeError("SSH server did not start")

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._start())
        self.ready.set()
        self.loop.run_forever()

    async def _start(self):
        vm = self

        class Server(asyncssh.SSHServer):
            def begin_auth(self, username):
                return True

            def password_auth_supported(self):
                return True

            def validate_password(self, username, password):
                return password == PASSWORD

            def public_key_auth_supported(self):
                return True

            def validate_public_key(self, username, key):
                ak = vm.home / ".ssh" / "authorized_keys"
                if not ak.exists():
                    return False
                for line in ak.read_text().splitlines():
                    try:
                        if asyncssh.import_public_key(line).public_data == key.public_data:
                            return True
                    except (asyncssh.KeyImportError, ValueError):
                        continue
                return False

        self.server = await asyncssh.create_server(
            Server, "127.0.0.1", 0,
            server_host_keys=[asyncssh.generate_private_key("ssh-ed25519")],
            process_factory=self._handle, encoding=None)
        self.port = self.server.sockets[0].getsockname()[1]

    async def _handle(self, process):
        env = {"HOME": str(self.home), "PATH": self.path, "USER": "tester", "SHELL": self.shell,
               "SSH_CONNECTION": "127.0.0.1 1 127.0.0.1 22", "STUB_REMOTE_LOG": str(self.log),
               "STUB_RECORDER": os.environ["STUB_RECORDER"]}
        if process.term_type:
            env["TERM"] = process.term_type
        cmd = process.command
        argv = [self.shell, "-c", cmd] if cmd is not None else [self.shell, "-l"]
        proc = await asyncio.create_subprocess_exec(
            *argv, cwd=self.home, env=env, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        async def pump_in():
            try:
                while True:
                    data = await process.stdin.read(65536)
                    if not data:
                        break
                    proc.stdin.write(data)
                    await proc.stdin.drain()
            except (asyncssh.BreakReceived, asyncssh.TerminalSizeChanged, BrokenPipeError,
                    ConnectionResetError):
                pass
            finally:
                proc.stdin.close()

        async def pump_out(src, dst):
            while True:
                data = await src.read(65536)
                if not data:
                    break
                dst.write(data)

        feeder = asyncio.ensure_future(pump_in())
        await asyncio.gather(pump_out(proc.stdout, process.stdout), pump_out(proc.stderr, process.stderr))
        rc = await proc.wait()
        feeder.cancel()
        process.exit(rc)

    def close(self):
        if self.loop.is_closed():
            return

        def stop():
            self.server.close()
            self.loop.stop()
        self.loop.call_soon_threadsafe(stop)
        self.thread.join(10)
        self.loop.close()


@unittest.skipUnless(asyncssh, "asyncssh not installed")
@unittest.skipUnless(shutil.which("ssh") and shutil.which("ssh-keygen"), "OpenSSH client not installed")
class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        # Use the real OpenSSH client, kept away from the user's ~/.ssh and agent.
        os.remove(self.sb.bin / "ssh")
        write_exe(self.sb.bin / "ssh",
                  f'#!/bin/sh\nexec {shutil.which("ssh")} -F /dev/null -o LogLevel=ERROR "$@"\n')
        askpass = write_exe(self.sb.tmp / "askpass", f"#!/bin/sh\necho {PASSWORD}\n")
        self.sb.env.update({"SSH_ASKPASS": str(askpass), "SSH_ASKPASS_REQUIRE": "force",
                            "DISPLAY": ":0", "SSH_AUTH_SOCK": ""})
        os.environ["STUB_RECORDER"] = str(self.sb.recorder)
        for tool in ("sudo", "apt-get", "tmux"):
            self.sb.remote_tool(tool)
        self.sb.remote_tool("curl", stubs.CURL)
        self.vm = FakeVM(self.sb.remote_home, str(self.sb.remote_bin), self.sb.remote_log)
        self.addCleanup(self.vm.close)
        self.sb.run("add", "vm", "--host", "127.0.0.1", "--port", str(self.vm.port), "--user", "tester",
                    "--dir", "~/project dir", check=0)
        # DISPLAY is set for SSH_ASKPASS: no desktop notifications here.
        self.sb.run("notify", "vm", "off", check=0)

    def test_setup_connect_doctor(self):
        r = self.sb.run("setup", "vm", timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("installing", r.stderr)
        self.assertIn("key login works", r.stderr)
        pub = (self.sb.home / ".ssh" / "vmclaude_ed25519.pub").read_text()
        self.assertEqual((self.sb.remote_home / ".ssh" / "authorized_keys").read_text(), pub)
        self.assertTrue((self.sb.remote_home / ".local" / "bin" / "claude").exists())
        self.assertIn("vmclaude autostart", (self.sb.remote_home / ".bashrc").read_text())

        # The host key is pinned under the profile's alias in vmclaude's own file.
        kh = (self.sb.conf / "known_hosts").read_text()
        self.assertTrue(kh.startswith("vmclaude-vm ssh-ed25519 "), kh)

        # Without the password now: the key must do.
        self.sb.env.pop("SSH_ASKPASS")
        self.sb.remote_log.write_text("")
        r = self.sb.run("vm", "-p", "it's $HOME", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        proj = self.sb.remote_home / "project dir"
        claude = self.sb.remote_home / ".local" / "bin" / "claude"
        self.assertEqual(self.sb.remote_calls(), [
            f"tmux [new-session] [-A] [-s] [claude] [-c] [{proj}] {WRAP}[{self.sb.remote_home}/.config/vmclaude/claude-env] "
            f"[{claude}] [-p] [it's $HOME] cwd=[{proj}]"])

        r = self.sb.run("doctor", "vm", timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ok    key login as tester", r.stdout)
        self.assertIn("ok    Claude Code on the VM: 9.9.9 (Claude Code)", r.stdout)
        self.assertIn("ok    autostart on SSH login: on", r.stdout)

        r = self.sb.run("shell", "vm", "echo", "$HOME", timeout=60)
        self.assertEqual(r.stdout, f"{self.sb.remote_home}\n")

    def test_changed_host_key_is_refused_until_forgotten(self):
        self.sb.run("setup", "vm", "--no-install", "--no-autostart", timeout=60, check=0)
        self.sb.remote_tool("claude")
        self.vm.close()
        self.vm = FakeVM(self.sb.remote_home, str(self.sb.remote_bin), self.sb.remote_log)  # new host key
        self.addCleanup(self.vm.close)
        self.sb.run("add", "vm", "--port", str(self.vm.port), check=0)
        r = self.sb.run("vm", timeout=60)
        self.assertEqual(r.returncode, 255)
        self.assertIn("vmclaude doctor vm", r.stderr)
        self.sb.run("forget", "vm", check=0)
        r = self.sb.run("vm", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_wrong_password(self):
        write_exe(self.sb.tmp / "askpass", "#!/bin/sh\necho wrong\n")
        r = self.sb.run("setup", "vm", timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn("could not install the key", r.stderr)


if __name__ == "__main__":
    unittest.main()
