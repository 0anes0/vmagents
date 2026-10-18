"""What the terminal UI (vmagents ui) builds on, and what scripts can use too:
list/images/snapshots --json, ports, create/setup --agents/--ports, resize
and open --lan. Against the fake ssh, virsh and VM."""
import json
import socket

from tests.helpers import VMAGENTS
from tests.ptyrun import run_in_pty
from tests.test_create import CreateBase
from tests.test_extras import free_pair
from tests.test_stop import Base


class JsonTests(Base):
    def test_list(self):
        (self.sb.tmp / "virsh.state.snaps").write_text(json.dumps([["auto-1", "2026-10-16 09:00:00 +0300", "shutoff", ""]]))
        self.sb.run("add", "h", "--host", "192.0.2.7", "--user", "dev", "--port", "2222", "--dir", 'my "dir"', check=0)
        with open(self.sb.conf / "hosts" / "vm.conf", "a") as f:
            f.write("PORTS=3000,5173\nAGENT=codex\nAGENTS=claude,codex\nIDLE=30\n")
        vms = {v["name"]: v for v in json.loads(self.sb.run("list", "--json", check=0).stdout)}
        vm, h = vms["vm"], vms["h"]
        self.assertEqual((vm["state"], vm["memory_mb"], vm["cpus"], vm["snapshots"]), ("running", 4096, 2, 1))
        self.assertEqual((vm["ports"], vm["agent"], vm["agents"], vm["idle"]), ([3000, 5173], "codex", ["claude", "codex"], 30))
        self.assertEqual((vm["autostop"], vm["notify"], vm["clipboard"], vm["created"]), (True, True, True, False))
        self.assertEqual((vm["cpu_ns"], vm["rss_mb"]), (7000000000, 2150))  # running: how busy
        self.assertEqual((h["cpu_ns"], h["rss_mb"]), (None, None))
        self.assertEqual((h["state"], h["memory_mb"], h["host"], h["port"], h["dir"]), (None, None, "192.0.2.7", 2222, 'my "dir"'))
        self.assertEqual(json.loads(self.sb.run("list", "--json", env={"HOME": str(self.sb.tmp / "empty")}, check=0).stdout), [])

    def test_snapshots(self):
        (self.sb.tmp / "virsh.state.snaps").write_text(json.dumps([["snap-1", "2026-10-16 09:00:00 +0300", "running", "a \"note\""]]))
        self.assertEqual(json.loads(self.sb.run("snapshots", "vm", "--json", check=0).stdout),
                         [{"name": "snap-1", "time": "2026-10-16 09:00:00", "state": "running", "description": 'a "note"'}])


class ImagesJsonTests(CreateBase):
    def test_images_json(self):
        r = json.loads(self.sb.run("images", "--json", check=0).stdout)
        self.assertEqual([i["name"] for i in r["images"]], ["debian13", "debian12", "ubuntu24.04", "arch"])
        self.assertFalse(r["images"][0]["downloaded"])
        host = r["host"]
        self.assertTrue(host["libvirt"])
        self.assertEqual(host["missing"], [])
        self.assertGreater(host["memory_mb"], 0)
        self.assertEqual(host["agents"], ["claude", "codex", "gemini", "opencode", "aider"])

    def test_create_with_agents_and_ports(self):
        r = self.sb.run("create", "box", "--agents", "codex,claude", "--ports", "3000, 8080", "--no-setup", check=0)
        self.assertIn("Next: vmagents setup box --agents codex,claude", r.stdout)
        self.assertIn("PORTS=3000,8080\n", (self.sb.conf / "hosts" / "box.conf").read_text())
        self.assertIn("--agents takes", self.sb.run("create", "c", "--agents", "copilot", "--no-setup").stderr)
        self.assertIn("--ports takes", self.sb.run("create", "c", "--ports", "http", "--no-setup").stderr)


class PortsTests(Base):
    def test_ports_command(self):
        self.assertEqual(self.sb.run("ports", "vm", check=0).stdout, "none\n")
        self.assertIn("ports of the VM are ports here too: 3000, 5173", self.sb.run("ports", "vm", "3000,5173", check=0).stdout)
        self.assertIn("PORTS=3000,5173\n", self.profile())
        self.assertEqual(self.sb.run("ports", "vm", "web").returncode, 2)
        self.assertEqual(self.sb.run("ports", "vm", "70000").returncode, 2)
        self.sb.run("ports", "vm", "off", check=0)
        self.assertNotIn("PORTS=", self.profile())

    def test_connect_forwards_them(self):
        p = free_pair()
        held = socket.socket()
        held.bind(("127.0.0.1", p + 1))
        held.listen(1)
        self.addCleanup(held.close)
        self.sb.run("ports", "vm", f"{p},{p + 1}", check=0)
        r = self.sb.run("vm", "--keep", check=0)
        argv = self.sb.calls("ssh")[0]["argv"]
        self.assertIn(f"127.0.0.1:{p}:localhost:{p}", argv)
        self.assertNotIn(f"127.0.0.1:{p + 1}:localhost:{p + 1}", argv)
        self.assertIn(f"Ports of vm here: http://localhost:{p}", r.stderr)
        self.assertIn(f"port {p + 1} is in use on this computer; not forwarded this time", r.stderr)

    def test_open_uses_them_and_lan(self):
        self.assertIn("or set some: vmagents ports vm 3000", self.sb.run("open", "vm").stderr)
        p = free_pair()
        self.sb.run("ports", "vm", str(p), check=0)
        out = run_in_pty([str(VMAGENTS), "open", "vm", "--lan", "--no-browser", "--keep"], self.sb.env,
                         str(self.sb.tmp), answers=[("Stop with Ctrl-C.", "\x03")])
        self.assertIn(f"Port {p} of vm: http://localhost:{p}", out)
        self.assertIn("on your network too: http://", out)
        fwd = [c for c in self.sb.calls("ssh") if "-N" in c["argv"]][0]["argv"]
        self.assertIn(f"0.0.0.0:{p}:localhost:{p}", fwd)


class ResizeTests(Base):
    def config(self):
        return json.loads((self.sb.tmp / "virsh.state.config").read_text())

    def test_resize(self):
        r = self.sb.run("resize", "vm", "--memory", "8192")
        self.assertEqual(r.returncode, 1)
        self.assertIn("resizing needs it off. Add --stop", r.stderr)
        r = self.sb.run("resize", "vm", "--memory", "8192", "--cpus", "4", "--stop", check=0)
        self.assertIn("VM testvm now has 8192 MB and 4 CPUs.", r.stdout)
        self.assertEqual(self.config(), {"memory": 8192, "cpus": 4})
        cmds = self.virsh_cmds()
        self.assertLess(cmds.index("shutdown"), cmds.index("setmaxmem"))
        self.sb.clear_log()
        self.sb.run("resize", "vm", "--cpus", "1", check=0)  # off now; fewer: the count first
        self.assertEqual([c for c in self.virsh_cmds() if c == "setvcpus"], ["setvcpus", "setvcpus"])
        argv = [c["argv"] for c in self.sb.calls("virsh") if c["argv"][2] == "setvcpus"]
        self.assertNotIn("--maximum", argv[0])
        self.assertIn("--maximum", argv[1])
        self.assertEqual(self.sb.run("resize", "vm").returncode, 2)
        self.assertIn("takes a whole number", self.sb.run("resize", "vm", "--memory", "lots").stderr)


class SetupAgentsTests(Base):
    def test_setup_agents(self):
        r = self.sb.run("setup", "vm", "--agents", "codex,gemini", "--no-autostart", check=0)
        self.assertIn("[2/3] tmux and codex, gemini", r.stderr)
        scripts = [c["argv"][-1] for c in self.sb.calls("ssh")]
        install = [s for s in scripts if "Installing Claude Code" in s][0]
        self.assertTrue(install.endswith(" 'no'"))  # Claude left out
        self.assertTrue(any(s.endswith(" 'codex'") and "chatgpt.com/codex" in s for s in scripts))
        self.assertTrue(any(s.endswith(" 'gemini'") for s in scripts))
        self.assertIn("AGENT=codex\n", self.profile())
        self.assertIn("AGENTS=codex,gemini\n", self.profile())
        self.assertIn("Open codex on the VM with:  vmagents vm", r.stdout)
        self.assertEqual(self.sb.run("setup", "vm", "--agents", "codex,bard").returncode, 2)
