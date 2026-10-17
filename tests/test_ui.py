"""The terminal UI (vmclaude ui), driven with Textual's test pilot against a
fake vmclaude that answers --json and records what the UI runs. Needs
Textual (skipped otherwise): uv run --with 'textual>=8,<9' python -m unittest
tests.test_ui"""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.helpers import write_exe
from tests.test_idle_notify import var

try:
    import textual  # noqa: F401
    HAVE_TEXTUAL = True
except ImportError:
    HAVE_TEXTUAL = False

FAKE = r'''#!/usr/bin/env python3
import json, os, signal, sys, time
d = os.environ["FAKE_UI_DIR"]
a = sys.argv[1:]
with open(os.path.join(d, "calls.jsonl"), "a") as f:
    f.write(json.dumps(a) + "\n")
def show(name):
    sys.stdout.write(open(os.path.join(d, name)).read())
if a[:2] == ["list", "--json"]: show("list.json")
elif a[:2] == ["images", "--json"]: show("images.json")
elif a[:1] == ["snapshots"]: show("snaps.json")
elif a[:1] == ["create"]:
    print("Creating VM " + a[1], flush=True)
    print("Done. Open Claude on the VM with:  vmclaude " + a[1], flush=True)
    sys.exit(int(os.environ.get("FAKE_CREATE_RC", "0")))
elif a[:1] == ["open"]:
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    for p in [x for x in a[2:] if x.isdigit()]:
        print(f"Port {p} of {a[1]}: http://localhost:{p}", flush=True)
    print("Stop with Ctrl-C.", flush=True)
    time.sleep(30)
else:
    print("ok")
'''

VM = {"name": "dev", "default": True, "host": "", "user": "me", "port": 22, "domain": "dev", "uri": "qemu:///system",
      "os": "linux", "dir": "", "session": "claude", "agent": "claude", "agents": ["claude"], "ports": [3000],
      "autostop": True, "notify": True, "clipboard": True, "idle": 30, "autosnap": 3, "created": True,
      "state": "running", "memory_mb": 4096, "cpus": 2, "snapshots": 2}
IMAGES = {"images": [{"name": "debian13", "description": "Debian 13", "downloaded": True},
                     {"name": "arch", "description": "Arch Linux", "downloaded": False}],
          "host": {"memory_mb": 16384, "memory_available_mb": 9000, "cpus": 8, "libvirt": True, "pool": "default",
                   "pool_available_gb": 100, "missing": [], "agents": ["claude", "codex", "gemini", "aider"]}}
SNAPS = [{"name": "auto-1", "time": "2026-10-16 09:00:00", "state": "shutoff", "description": ""},
         {"name": "snap-2", "time": "2026-10-16 10:00:00", "state": "running", "description": "before refactor"}]


@unittest.skipUnless(HAVE_TEXTUAL, "needs Textual")
class UITests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="vmclaude-ui-"))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.write(list=[VM, dict(VM, name="srv", default=False, domain="", host="192.0.2.5", state=None,
                                  memory_mb=None, cpus=None, created=False, ports=[])])
        self.write(images=IMAGES, snaps=SNAPS)
        fake = write_exe(self.d / "vmclaude", FAKE)
        os.environ["FAKE_UI_DIR"] = str(self.d)
        os.environ["VMCLAUDE_BIN"] = str(fake)
        src = self.d / "ui.py"
        src.write_text(var("UI_PY"))
        spec = importlib.util.spec_from_file_location("vmclaude_ui", src)
        self.ui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.ui)
        self.app = self.ui.VmClaudeUI()
        self.ran = []
        self.app.interactive = lambda args: self.ran.append(args)  # no terminal to hand over in tests

    def write(self, **files):
        for name, data in files.items():
            (self.d / f"{name}.json").write_text(json.dumps(data))

    def calls(self, first=None):
        f = self.d / "calls.jsonl"
        calls = [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []
        return [c for c in calls if first is None or c[:1] == [first]]

    async def wait_for(self, pilot, cond, seconds=5):
        for _ in range(int(seconds * 10)):
            if cond():
                return True
            await pilot.pause(0.1)
        return cond()

    def start(self):
        return self.app.run_test(size=(120, 40))

    async def ready(self, pilot):
        await self.wait_for(pilot, lambda: self.app.vms and self.app.info)

    async def test_list_and_details(self):
        async with self.start() as pilot:
            await self.ready(pilot)
            table = self.app.query_one("#vms")
            self.assertEqual(table.row_count, 2)
            details = str(self.app.query_one("#details").render())
            self.assertIn("dev", details)
            self.assertIn("4 GB RAM · 2 CPUs · 2 snapshots", details)
            self.assertIn("Ports: 3000 (while connected)", details)
            await pilot.press("down")
            await pilot.pause(0.2)
            self.assertIn("me@192.0.2.5", str(self.app.query_one("#details").render()))

    async def test_open_and_agents(self):
        async with self.start() as pilot:
            await self.ready(pilot)
            await pilot.press("enter")
            await pilot.pause(0.2)
            self.assertEqual(self.ran, [["dev", "--hold"]])
            await pilot.press("a")
            await pilot.pause(0.2)
            await pilot.press("down", "enter")  # Codex
            await pilot.pause(0.2)
            self.assertEqual(self.ran[-1], ["dev", "--hold", "--codex"])

    async def test_new_vm(self):
        async with self.start() as pilot:
            await self.ready(pilot)
            await pilot.press("n")
            await pilot.pause(0.3)
            form = self.app.screen
            await pilot.press("ctrl+s")
            await pilot.pause(0.2)
            self.assertIn("Give the VM a name", str(form.query_one("#error").render()))
            for name, err in (("dev", "There is a VM named dev"), ("a b", "letters, digits")):
                form.query_one("#name").value = name
                await pilot.press("ctrl+s")
                await pilot.pause(0.2)
                self.assertIn(err, str(form.query_one("#error").render()))
            form.query_one("#name").value = "web"
            form.query_one("#image").value = "arch"
            form.query_one("#memory").value = 8192
            form.query_one("#cpus").value = 4
            form.query_one("#disk").value = "40"
            form.query_one("#agent-codex").value = True
            form.query_one("#ports").value = "3000,5173"
            form.query_one("#idle").value = 0
            await pilot.pause(0.2)
            self.assertIn("vmclaude create web --image arch --memory 8192 --cpus 4 --disk 40 --agents claude,codex "
                          "--idle off --ports 3000,5173", str(form.query_one("#command").render()))
            await pilot.press("ctrl+s")
            await self.wait_for(pilot, lambda: getattr(self.app.screen, "rc", None) is not None)
            screen = self.app.screen
            self.assertEqual(screen.rc, 0)
            self.assertEqual(self.calls("create")[-1], ["create", "web", "--image", "arch", "--memory", "8192",
                                                        "--cpus", "4", "--disk", "40", "--agents", "claude,codex",
                                                        "--idle", "off", "--ports", "3000,5173"])
            self.assertFalse(screen.query_one("#open").disabled)
            await pilot.click("#login")
            self.assertEqual(self.ran[-1], ["login", "web"])

    async def test_new_vm_checks(self):
        async with self.start() as pilot:
            await self.ready(pilot)
            await pilot.press("n")
            await pilot.pause(0.3)
            form = self.app.screen
            form.query_one("#name").value = "x"
            for field, value, err in (("#disk", "200", "the libvirt pool has 100 GB free"),
                                      ("#ports", "web", "numbers separated by commas"),
                                      ("#agent-claude", False, "at least one AI assistant")):
                if field == "#ports":
                    form.query_one("#disk").value = "20"
                if field == "#agent-claude":
                    form.query_one("#ports").value = ""
                form.query_one(field).value = value
                await pilot.press("ctrl+s")
                await pilot.pause(0.2)
                self.assertIn(err, str(form.query_one("#error").render()))
            self.assertEqual(self.calls("create"), [])

    async def test_failed_create(self):
        os.environ["FAKE_CREATE_RC"] = "1"
        self.addCleanup(os.environ.pop, "FAKE_CREATE_RC")
        async with self.start() as pilot:
            await self.ready(pilot)
            await pilot.press("n")
            await pilot.pause(0.3)
            self.app.screen.query_one("#name").value = "web"
            await pilot.press("ctrl+s")
            await self.wait_for(pilot, lambda: getattr(self.app.screen, "rc", None) is not None)
            self.assertIn("failed", str(self.app.screen.query_one("#status").render()))
            self.assertTrue(self.app.screen.query_one("#open").disabled)

    async def test_start_stop_snapshot_undo_resize(self):
        async with self.start() as pilot:
            await self.ready(pilot)
            await pilot.press("t")
            await self.wait_for(pilot, lambda: self.calls("stop"))
            self.assertEqual(self.calls("stop"), [["stop", "dev"]])
            await pilot.press("p")
            await pilot.pause(0.2)
            await pilot.press(*"before x", "enter")
            await self.wait_for(pilot, lambda: self.calls("snapshot"))
            self.assertEqual(self.calls("snapshot"), [["snapshot", "dev", "before x"]])
            await pilot.press("u")
            await pilot.pause(0.3)
            await pilot.press("down", "enter")  # newest first: snap-2, then auto-1
            await pilot.pause(0.2)
            await pilot.click("#yes")
            await self.wait_for(pilot, lambda: self.calls("undo"))
            self.assertEqual(self.calls("undo"), [["undo", "dev", "auto-1", "--yes"]])
            await pilot.press("r")
            await pilot.pause(0.2)
            self.app.screen.query_one("#memory").value = 8192
            await pilot.click("#ok")
            await self.wait_for(pilot, lambda: self.calls("resize"))
            self.assertEqual(self.calls("resize"), [["resize", "dev", "--memory", "8192", "--cpus", "2", "--stop"]])

    async def test_not_libvirt(self):
        async with self.start() as pilot:
            await self.ready(pilot)
            await pilot.press("down", "t", "u", "r")
            await pilot.pause(0.3)
            self.assertEqual(self.calls("start") + self.calls("stop") + self.calls("resize"), [])

    async def test_ports(self):
        async with self.start() as pilot:
            await self.ready(pilot)
            await pilot.press("o")
            await pilot.pause(0.2)
            dialog = self.app.screen
            self.assertEqual(dialog.query_one("#text").value, "3000")
            dialog.query_one("#text").value = "3000,8080"
            dialog.query_one("#browser").value = False
            await pilot.click("#ok")
            await self.wait_for(pilot, lambda: len(self.app.forwards.get("dev", [])) == 2)
            self.assertIn(["open", "dev", "3000", "8080", "--keep", "--no-browser"], self.calls("open"))
            self.assertIn(["ports", "dev", "3000,8080"], self.calls("ports"))  # "every time" was on
            self.assertIn("port 8080 at http://localhost:8080", str(self.app.query_one("#details").render()))
            proc = self.app.forwards["dev"][0][0]
            await pilot.press("o")
            await pilot.pause(0.2)
            await pilot.click("#yes")  # stop
            await self.wait_for(pilot, lambda: proc.poll() is not None)
            self.assertEqual(proc.poll(), 0)
            self.assertEqual(self.app.forwards["dev"], [])

    async def test_delete(self):
        async with self.start() as pilot:
            await self.ready(pilot)
            await pilot.press("d")
            await pilot.pause(0.2)
            self.assertTrue(self.app.screen.query_one("#yes").disabled)
            await pilot.press(*"dev")
            await pilot.pause(0.1)
            await pilot.press("enter")
            await self.wait_for(pilot, lambda: self.calls("delete"))
            self.assertEqual(self.calls("delete"), [["delete", "dev", "--yes"]])
            await pilot.press("down", "d")  # not made by vmclaude: only the profile
            await pilot.pause(0.2)
            await pilot.click("#yes")
            await self.wait_for(pilot, lambda: self.calls("rm"))
            self.assertEqual(self.calls("rm"), [["rm", "srv"]])

    async def test_no_vms(self):
        self.write(list=[])
        async with self.start() as pilot:
            await self.wait_for(pilot, lambda: self.app.info)
            await pilot.pause(0.5)
            self.assertIn("No VMs yet", str(self.app.query_one("#details").render()))
            await pilot.press("enter", "t")
            await pilot.pause(0.2)
            self.assertEqual(self.ran, [])
