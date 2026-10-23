"""phone: the QR code, the web server (page, list, WebSocket terminal, wrong
keys) and the SSH forwards, against fake VMs and a fake vmagents."""
import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from tests.helpers import SandboxTest, free_port, listening_port, write_exe
from tests.test_idle_notify import var

QR = var("QR_PY")
PHONE = var("PHONE_PY")


def qr_rows(text):
    ns = {}
    exec(compile(QR.replace('if __name__ == "__main__":', "if False:"), "qr", "exec"), ns)
    return ns


class QRTests(unittest.TestCase):
    def setUp(self):
        self.qr = qr_rows("")

    def digest(self, text):
        m = self.qr["matrix"](text)
        return len(m), hashlib.sha256("".join("".join(map(str, r)) for r in m).encode()).hexdigest()[:16]

    def test_known_codes(self):
        # Checked with the qrcode library (all masks, versions 1 to 9) and decoded with jsQR.
        self.assertEqual(self.digest("A"), (21, "2092585037e9da56"))
        self.assertEqual(self.digest("http://100.101.102.103:7700/#t=abcdefghijklmnopqrstuvwxyz0123456789ABCD"),
                         (37, "ba941350f1ec8c54"))
        self.assertEqual(self.digest("https://example.com/" + "x" * 120), (49, "631c90ff89ad09c1"))
        with self.assertRaises(ValueError):
            self.qr["matrix"]("x" * 200)

    def test_same_as_the_qrcode_library(self):
        try:
            import qrcode
            from qrcode.util import QRData, MODE_8BIT_BYTE
        except ImportError:
            self.skipTest("the qrcode library is not installed")
        for text in ("A", "http://100.64.0.1:7700/#t=" + "k" * 32, "y" * 150):
            for mask in range(8):
                ours = self.qr["matrix"](text, mask)
                q = qrcode.QRCode(version=(len(ours) - 17) // 4, error_correction=qrcode.constants.ERROR_CORRECT_M,
                                  mask_pattern=mask, border=0)
                q.add_data(QRData(text.encode(), mode=MODE_8BIT_BYTE), optimize=0)
                q.make(fit=False)
                self.assertEqual(ours, [[int(bool(v)) for v in row] for row in q.modules])

    def test_half_blocks(self):
        rows = self.qr["text_rows"]("A")
        self.assertEqual(len(rows), (21 + 4 + 1) // 2)
        self.assertTrue(all(len(r) == 25 for r in rows))
        self.assertEqual(rows[0], "█" * 25)  # the quiet zone is light


# A fake vmagents for the server: "list --json", a terminal that says what
# it is and echoes lines, and "__addr NAME" for the SSH forwards.
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
if a[:2] == ["list", "--json"]:
    print(json.dumps([{"name": "dev", "state": "running", "os": "linux", "agent": "codex", "domain": "dev",
                       "default": True, "user": "me", "try": ""},
                      {"name": "dev-t1", "state": "running", "os": "linux", "agent": "claude", "domain": "dev-t1",
                       "default": False, "try": "dev"}]))
elif a[:1] == ["__addr"]:
    print("127.0.0.1", os.environ["FAKE_SSH_PORT"])
else:
    rows, cols = os.popen("stty size").read().split()
    print("session:", " ".join(a), "size:", cols, rows, "tty:", os.isatty(0), flush=True)
    for line in sys.stdin:
        if line.strip() == "exit":
            sys.exit(3)
        print("you typed:", line.strip(), flush=True)
'''


class WS:
    """A small WebSocket client, like a browser's."""

    def __init__(self, port, query):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET /ws?{query} HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        self.buf = b""
        while b"\r\n\r\n" not in self.buf:
            self.buf += self.s.recv(4096)
        head, self.buf = self.buf.split(b"\r\n\r\n", 1)
        self.status = head.split(b"\r\n")[0].decode()
        want = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        self.accepted = b"Sec-WebSocket-Accept: " + want in head
        self.out, self.texts, self.closed = b"", [], False

    def send(self, data, op=1):
        m = os.urandom(4)
        n = len(data)
        head = bytes([128 | op]) + (bytes([128 | n]) if n < 126 else bytes([128 | 126]) + struct.pack(">H", n))
        self.s.sendall(head + m + bytes(b ^ m[i % 4] for i, b in enumerate(data)))

    def read_until(self, cond, seconds=10):
        end = time.time() + seconds
        self.s.settimeout(0.2)
        while not cond() and not self.closed and time.time() < end:
            try:
                d = self.s.recv(65536)
                if not d:
                    self.closed = True
                self.buf += d
            except socket.timeout:
                pass
            while len(self.buf) >= 2:
                n, off = self.buf[1] & 127, 2
                if n == 126:
                    n, off = struct.unpack(">H", self.buf[2:4])[0], 4
                if len(self.buf) < off + n:
                    break
                op, data, self.buf = self.buf[0] & 15, self.buf[off:off + n], self.buf[off + n:]
                if op == 2:
                    self.out += data
                elif op == 1:
                    self.texts.append(data.decode())
                elif op == 8:
                    self.closed = True
        return cond()


class ServerTests(SandboxTest):
    def setUp(self):
        super().setUp()
        self.dir = self.sb.tmp / "phone"
        self.dir.mkdir()
        (self.dir / "token").write_text("sekret-key\n")
        fake = write_exe(self.sb.tmp / "fake-vmagents", FAKE)
        self.port = free_port()
        self.ssh_srv, ssh_port = listening_port()
        self.addCleanup(self.ssh_srv.close)
        env = dict(os.environ, VMAGENTS_CACHE=str(self.sb.tmp), FAKE_SSH_PORT=str(ssh_port))
        self.proc = subprocess.Popen(["python3", "-c", PHONE, str(fake), str(self.dir), "127.0.0.1", str(self.port)],
                                     env=env, stdin=subprocess.DEVNULL)
        self.addCleanup(self.stop)
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=1).close()
                break
            except OSError:
                time.sleep(0.1)

    def stop(self):
        self.proc.terminate()
        self.proc.wait(5)

    def get(self, path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=10) as r:
                return r.status, r.headers, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read().decode()

    def test_page_and_list(self):
        status, headers, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("xterm@5.5.0", body)
        self.assertIn('integrity="sha384-', body)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.get("/api/vms?t=wrong")[0], 403)
        self.assertEqual(self.get("/api/vms")[0], 403)
        status, _, body = self.get("/api/vms?t=sekret-key")
        self.assertEqual(status, 200)
        vms = json.loads(body)
        self.assertEqual([v["name"] for v in vms], ["dev"])  # not the copies of try
        self.assertEqual(vms[0]["agent"], "codex")
        self.assertNotIn("user", vms[0])
        self.assertEqual(self.get("/nope")[0], 404)
        self.assertIn("wrong key", (self.sb.tmp / "phone.log").read_text())

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_page_script(self):
        body = self.get("/")[2]
        script = self.sb.tmp / "page.js"
        script.write_text(body[body.index('<script>\n"use strict"') + 8:body.rindex("</script>")])
        r = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_terminal(self):
        ws = WS(self.port, "t=sekret-key&vm=dev&kind=agent&cols=50&rows=20")
        self.assertEqual(ws.status, "HTTP/1.1 101 Switching Protocols")
        self.assertTrue(ws.accepted)
        self.assertTrue(ws.read_until(lambda: b"session: connect dev size: 50 20 tty: True" in ws.out), ws.out)
        ws.send(b'r{"cols": 70, "rows": 30}')
        ws.send(b"ihello\r")
        self.assertTrue(ws.read_until(lambda: b"you typed: hello" in ws.out), ws.out)
        ws.send(b"iexit\r")
        self.assertTrue(ws.read_until(lambda: ws.closed))
        self.assertEqual(ws.texts, ["x3"])  # the exit code
        shell = WS(self.port, "t=sekret-key&vm=dev&kind=shell")
        self.assertTrue(shell.read_until(lambda: b"session: shell dev size: 80 24" in shell.out), shell.out)
        shell.s.close()  # the phone goes away: the terminal here ends
        time.sleep(1)
        log = (self.sb.tmp / "phone.log").read_text()
        self.assertIn("opened agent on dev", log)
        self.assertIn("closed shell on dev", log)
        bad = WS(self.port, "t=bad&vm=dev")
        self.assertFalse(bad.accepted)
        bad.s.close()
        ws.s.close()

    def test_ssh_forward(self):
        (self.dir / "ssh").write_text(f"dev {self.port + 1}\n")
        for _ in range(50):  # the server looks at the file every 2 s
            try:
                c = socket.create_connection(("127.0.0.1", self.port + 1), timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        c.settimeout(10)
        self.assertEqual(c.recv(100), b"SSH-2.0-OpenSSH_test\r\n")  # the VM's sshd, through it
        c.close()
        self.assertIn("SSH to dev", (self.sb.tmp / "phone.log").read_text())


class CommandTests(SandboxTest):
    def setUp(self):
        super().setUp()
        self.sb.env["XDG_RUNTIME_DIR"] = str(self.sb.tmp)  # its own server, not this computer's
        self.port = free_port()
        self.addCleanup(lambda: self.sb.run("phone", "off"))

    def test_needs_tailscale(self):
        # This computer may have Tailscale: a PATH with all but it.
        hide = self.sb.tmp / "no-tailscale"
        hide.mkdir()
        for d in ("/usr/local/bin", "/usr/bin", "/bin"):
            for f in Path(d).iterdir() if Path(d).is_dir() else ():
                if f.name != "tailscale" and not (hide / f.name).exists():
                    (hide / f.name).symlink_to(f)
        self.sb.env["PATH"] = f"{self.sb.bin}:{hide}"
        r = self.sb.run("phone")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Tailscale is not installed", r.stderr)
        self.assertIn("vmagents phone --lan", r.stderr)
        write_exe(self.sb.bin / "tailscale", "#!/bin/sh\nexit 1\n")
        self.assertIn("Tailscale is not connected", self.sb.run("phone").stderr)

    def test_on_off_new(self):
        write_exe(self.sb.bin / "tailscale", '#!/bin/sh\n[ "$1 $2" = "ip -4" ] && echo 127.0.0.1\n')
        r = self.sb.run("phone", "--port", str(self.port), check=0)
        self.assertIn("over Tailscale", r.stdout)
        token = (self.sb.conf / "phone" / "token").read_text()
        self.assertRegex(token, r"^[A-Za-z0-9_-]{32}$")
        self.assertIn(f"http://127.0.0.1:{self.port}/#t={token}", r.stdout)
        self.assertEqual(oct((self.sb.conf / "phone").stat().st_mode & 0o777), "0o700")
        self.assertIn(f"PORT={self.port}", (self.sb.conf / "phone" / "conf").read_text())
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/vms?t={token}", timeout=10) as resp:
            self.assertEqual(json.loads(resp.read()), [])
        info = json.loads(self.sb.run("phone", "--json", check=0).stdout)  # the same server, remembered port
        self.assertEqual((info["port"], info["listen"], info["ssh"]), (self.port, "tailscale", []))
        self.assertTrue(all(set(row) <= set(" ▀▄█") for row in info["qr"]))
        new = json.loads(self.sb.run("phone", "--json", "--new", check=0).stdout)
        self.assertNotEqual(new["url"], info["url"])
        self.assertIn("Phone access is off", self.sb.run("phone", "off", check=0).stdout)
        with self.assertRaises(OSError):
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=3)
        self.assertIn("vmagents phone ssh NAME", self.sb.run("help", "phone", check=0).stdout)

    def test_ssh_key(self):
        self.sb.env["VMAGENTS_PHONE_ADDR"] = "127.0.0.1"
        self.sb.env["STUB_SSH_EXEC"] = "1"
        self.sb.run("add", "vm", "--host", "192.0.2.9", "--user", "me", "--os", "linux", check=0)
        key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPhone termius"
        (self.sb.conf / "phone").mkdir(parents=True)
        (self.sb.conf / "phone" / "conf").write_text(f"PORT={self.port}\n")
        self.assertIn("not an SSH public key", self.sb.run("phone", "ssh", "vm", "hello").stderr)
        r = self.sb.run("phone", "ssh", "vm", key, check=0)
        self.assertIn(f"host 127.0.0.1   port {self.port + 1}   user me", r.stdout)
        keys = self.sb.remote_home / ".ssh" / "authorized_keys"
        self.assertIn(key + "\n", keys.read_text())
        self.assertEqual((self.sb.conf / "phone" / "ssh").read_text(), f"vm {self.port + 1}\n")
        pub = self.sb.tmp / "app.pub"
        pub.write_text(key + "\r\n")
        self.sb.run("phone", "ssh", "vm", str(pub), check=0)  # from a file; again: same port, key once
        self.assertEqual(keys.read_text().count(key), 1)
        self.assertEqual((self.sb.conf / "phone" / "ssh").read_text(), f"vm {self.port + 1}\n")
        info = json.loads(self.sb.run("phone", "--json", check=0).stdout)
        self.assertEqual(info["ssh"], [{"name": "vm", "port": self.port + 1, "user": "me"}])
        self.assertIn("removed from vm", self.sb.run("phone", "ssh", "vm", "off", check=0).stdout)
        self.assertNotIn(key, keys.read_text())
        self.assertEqual((self.sb.conf / "phone" / "ssh").read_text(), "")
        self.assertIn("no SSH app", self.sb.run("phone", "ssh", "vm", "off").stderr)


if __name__ == "__main__":
    unittest.main()
