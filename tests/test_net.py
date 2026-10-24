"""The restricted network: the proxy (PROXY_PY) with real connections, and
"vmforai net" against a fake libvirt that keeps the VM's XML, its filter
and its card, and the fake VM (its proxy settings)."""
import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import time

from tests.helpers import free_port, listening_port, write_exe
from tests.helpers import SandboxTest
from tests.test_idle_notify import var


class Upstream(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"upstream got {self.path}".encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def ask(port, data):
    """Sends DATA to the proxy; after "200 Connection established" a request
    through the tunnel. Returns everything that came back."""
    with socket.create_connection(("127.0.0.1", port), timeout=5) as s:
        s.sendall(data)
        out = b""
        while b"\r\n\r\n" not in out and (chunk := s.recv(65536)):
            out += chunk
        if out.startswith(b"HTTP/1.1 200 Connection established"):
            s.sendall(b"GET /tunnel HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
        while chunk := s.recv(65536):
            out += chunk
        return out.decode("latin-1")


class ProxyTests(SandboxTest):
    def setUp(self):
        super().setUp()
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        self.up = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.allow = self.sb.tmp / "allow"
        self.allow.write_text(f"# test\n127.0.0.1:{self.up}\n*.example.test\nexact.test\n")
        self.log = self.sb.tmp / "log"
        self.state = self.sb.tmp / "domstate"
        self.state.write_text("running")
        write_exe(self.sb.bin / "virsh", f"#!/bin/sh\ncat {self.state}\n")
        self.port = free_port()
        # Allowed names that do not exist: refused by their DNS soon, or not.
        env = dict(os.environ, PATH=f"{self.sb.bin}:{os.environ['PATH']}", VMFORAI_PROXY_WATCH="0.2",
                   VMFORAI_PROXY_CONNECT_TIMEOUT="1")
        self.proc = subprocess.Popen([sys.executable, "-c", var("PROXY_PY"), str(self.allow), str(self.log),
                                      "127.0.0.1", str(self.port), "qemu:///system", "vm"], env=env)
        self.addCleanup(self.proc.kill)
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.05)

    def test_allowed_and_refused(self):
        out = ask(self.port, f"CONNECT 127.0.0.1:{self.up} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
        self.assertTrue(out.startswith("HTTP/1.1 200 Connection established"), out)
        self.assertIn("upstream got /tunnel", out)
        out = ask(self.port, f"GET http://127.0.0.1:{self.up}/plain?q=1 HTTP/1.1\r\nHost: x\r\n"
                             f"Proxy-Connection: keep-alive\r\nConnection: close\r\n\r\n".encode())
        self.assertIn("upstream got /plain?q=1", out)
        out = ask(self.port, f"CONNECT localhost:{self.up} HTTP/1.1\r\n\r\n".encode())
        self.assertIn(" 403 ", out)
        self.assertIn("localhost is not allowed from this VM", out)
        self.assertIn(f"localhost:{self.up}", self.log.read_text())
        # Patterns: *.domain and its subdomains, a plain name on 80 and 443 only.
        self.assertIn(" 502 ", ask(self.port, b"CONNECT a.b.example.test:443 HTTP/1.1\r\n\r\n"))  # allowed, no such host
        self.assertIn(" 502 ", ask(self.port, b"CONNECT example.test:443 HTTP/1.1\r\n\r\n"))
        self.assertIn(" 502 ", ask(self.port, b"CONNECT exact.test:443 HTTP/1.1\r\n\r\n"))
        self.assertIn(" 403 ", ask(self.port, b"CONNECT exact.test:22 HTTP/1.1\r\n\r\n"))
        self.assertIn(" 403 ", ask(self.port, b"CONNECT sub.exact.test:443 HTTP/1.1\r\n\r\n"))
        self.assertIn(" 403 ", ask(self.port, b"CONNECT badexample.test:443 HTTP/1.1\r\n\r\n"))
        self.assertIn(" 400 ", ask(self.port, b"GET /direct HTTP/1.1\r\n\r\n"))
        # The list is read again when it changes.
        time.sleep(0.05)
        with open(self.allow, "a") as f:
            f.write(f"localhost:{self.up}\n")
        os.utime(self.allow, (time.time() + 5, time.time() + 5))
        self.assertTrue(ask(self.port, f"CONNECT localhost:{self.up} HTTP/1.1\r\n\r\n".encode())
                        .startswith("HTTP/1.1 200"))

    def test_ends_with_the_vm(self):
        self.state.write_text("shut off")
        self.assertEqual(self.proc.wait(timeout=5), 0)


# Fake libvirt keeping the domain's XML as it is (dumpxml/define), its live
# card (update-device), filters (nwfilter-define) and one network.
VIRSH = r'''#!/usr/bin/env python3
import json, os, re, sys
args = sys.argv[1:]
if args[:1] == ["-c"]: args = args[2:]
path = os.environ["FAKE_LV"]
st = json.load(open(path))
with open(os.environ["STUB_LOG"], "a") as f:
    f.write(json.dumps({"prog": "virsh", "argv": args}) + "\n")
def save(): json.dump(st, open(path, "w"))
cmd, rest = args[0], [a for a in args[1:] if not a.startswith("--")]
if cmd == "domstate":
    print(st["state"]); sys.exit(0)
if cmd == "dumpxml":
    print(st["xml"] if "--inactive" in args else st.get("live", st["xml"])); sys.exit(0)
if cmd == "define":
    st["xml"] = open(rest[0]).read(); save(); sys.exit(0)
if cmd == "update-device":
    st["live_iface"] = open(rest[1]).read(); save(); sys.exit(0)
if cmd == "nwfilter-define":
    x = open(rest[0]).read()
    st.setdefault("filters", {})[re.search(r"name='([^']+)'", x).group(1)] = x; save(); sys.exit(0)
if cmd == "domiflist":
    print(" Interface   Type      Source    Model    MAC\n" + "-" * 40)
    print(" vnet0       network   default   virtio   52:54:00:00:00:01"); sys.exit(0)
if cmd == "net-dumpxml":
    print("<network>\n  <name>default</name>\n  <ip address='127.0.0.1' netmask='255.255.255.0'>\n  </ip>\n</network>")
    sys.exit(0)
if cmd == "net-dhcp-leases":
    print(" Expiry   MAC   Protocol   IP   Hostname   ID\n" + "-" * 20)
    print(" 2026-10-18 18:00:00   52:54:00:00:00:01   ipv4   127.0.0.1/24   vm   01"); sys.exit(0)
if cmd in ("snapshot-list", "snapshot-create-as", "start"):
    sys.exit(0)
print("unsupported", args, file=sys.stderr); sys.exit(1)
'''

DOMAIN_XML = """<domain type='kvm'>
  <name>vm</name>
  <devices>
    <interface type='network'>
      <mac address='52:54:00:00:00:01'/>
      <source network='default'/>
      <model type='virtio'/>
    </interface>
  </devices>
</domain>"""


class NetTests(SandboxTest):
    def setUp(self):
        super().setUp()
        self.listener, self.sshport = listening_port()
        self.addCleanup(self.listener.close)
        self.lv = self.sb.tmp / "lv.json"
        self.lv.write_text(json.dumps({"state": "running", "xml": DOMAIN_XML}))
        write_exe(self.sb.bin / "virsh", VIRSH)
        self.sb.env.update(FAKE_LV=str(self.lv), STUB_SSH_EXEC="1", XDG_RUNTIME_DIR=str(self.sb.tmp),
                           VMFORAI_PROXY_WATCH="0.3")
        self.sb.run("add", "vm", "--domain", "vm", "--port", str(self.sshport), "--os", "linux", check=0)
        self.addCleanup(self.stop_proxy)

    def stop_proxy(self):
        pid = self.sb.tmp / f"vmforai-proxy-{os.getuid()}-vm.lock.pid"
        if pid.exists():
            try:
                os.kill(int(pid.read_text()), 9)
            except OSError:
                pass

    def state(self):
        return json.loads(self.lv.read_text())

    def profile(self):
        return (self.sb.conf / "hosts" / "vm.conf").read_text()

    def test_restricted_then_open(self):
        self.assertIn("Network of vm: open", self.sb.run("net", "vm", check=0).stdout)
        r = self.sb.run("net", "vm", "restricted", check=0)
        self.assertIn("The network of vm is restricted", r.stdout)
        port = int(self.profile().split("NETPORT=")[1].split()[0])
        self.assertIn("NET=restricted\n", self.profile())
        st = self.state()
        f = st["filters"]["vmforai-restricted"]
        for rule in ("<udp dstipaddr='$GATEWAY' dstportstart='53'/>", "<tcp dstipaddr='$GATEWAY' dstportstart='$PROXY_PORT'/>",
                     "<tcp dstportstart='22'/>", "<rule action='drop' direction='inout' priority='500'><all/></rule>"):
            self.assertIn(rule, f)
        self.assertIn("<filterref filter='vmforai-restricted'>", st["xml"])
        self.assertIn("<parameter name='GATEWAY' value='127.0.0.1'/>", st["xml"])
        self.assertIn(f"<parameter name='PROXY_PORT' value='{port}'/>", st["xml"])
        self.assertIn("<filterref filter='vmforai-restricted'><parameter name='GATEWAY' value='127.0.0.1'/>",
                      st["live_iface"])  # the running VM's card too
        self.assertTrue(st["live_iface"].startswith("    <interface type='network'>"))
        env = (self.sb.remote_home / ".config" / "vmforai" / "proxy-env").read_text()
        self.assertIn(f"https_proxy=http://127.0.0.1:{port}\n", env)
        self.assertIn("NO_PROXY=localhost,127.0.0.1,::1\n", env)
        # The proxy runs here, and notes what it refuses.
        for _ in range(50):
            try:
                out = ask(port, b"CONNECT evil.example:443 HTTP/1.1\r\n\r\n")
                break
            except OSError:
                time.sleep(0.1)
        self.assertIn(" 403 ", out)
        listing = self.sb.run("net", "vm", check=0).stdout
        self.assertIn("Network of vm: restricted", listing)
        self.assertIn("*.anthropic.com", listing)
        self.assertIn("Refused lately:\n  evil.example:443", listing)
        self.assertIn("evil.example:443", self.sb.run("net", "vm", "blocked", check=0).stdout)
        # The list.
        self.sb.run("net", "vm", "allow", "Evil.Example", "*.corp.test:8443", check=0)
        allow = (self.sb.conf / "net" / "vm.allow").read_text()
        self.assertIn("\nevil.example\n*.corp.test:8443\n", allow)
        self.sb.run("net", "vm", "deny", "evil.example", check=0)
        self.assertNotIn("evil.example\n", (self.sb.conf / "net" / "vm.allow").read_text())
        self.assertIn("not a host name", self.sb.run("net", "vm", "allow", "a b").stderr)
        # Open again: no filter, no proxy settings, no proxy.
        self.assertIn("open again", self.sb.run("net", "vm", "open", check=0).stdout)
        st = self.state()
        self.assertNotIn("filterref", st["xml"])
        self.assertNotIn("filterref", st["live_iface"])
        self.assertFalse((self.sb.remote_home / ".config" / "vmforai" / "proxy-env").exists())
        self.assertIn("NET=open\n", self.profile())
        time.sleep(0.5)
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
        self.assertTrue(json.loads(self.sb.run("list", "--json", check=0).stdout)[0]["net"] == "open")

    def test_launcher_reads_the_proxy_settings(self):
        d = self.sb.remote_home / ".config" / "vmforai"
        d.mkdir(parents=True)
        (d / "proxy-env").write_text("HTTPS_PROXY=http://gw:1\n")
        (d / "codex-env").write_text("OPENAI_API_KEY=k\n")
        write_exe(self.sb.tmp / "codex", '#!/bin/sh\necho "$HTTPS_PROXY $OPENAI_API_KEY"\n')
        out = subprocess.run(["sh", "-c", var("CLAUDE_ENV_SH"), "x", str(d / "codex-env"), str(self.sb.tmp / "codex")],
                             capture_output=True, text=True).stdout
        self.assertEqual(out, "http://gw:1 k\n")

    def test_problems(self):
        self.assertEqual(self.sb.run("net", "vm", "closed").returncode, 2)
        self.sb.run("add", "h", "--host", "192.0.2.1", check=0)
        self.assertIn("needs a libvirt VM", self.sb.run("net", "h", "restricted").stderr)
        self.assertIn("vmforai net NAME", self.sb.run("help", "net", check=0).stdout)
