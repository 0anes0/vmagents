"""The README's pictures of the terminal UI (docs/ui*.png): the real UI of
../../vmforai, driven by Textual's pilot against a made-up vmforai that
answers with five VMs, a Claude Code session and a project's changes.
Each view is saved as SVG, then drawn to PNG by headless Chromium.

  uv run --no-project --with 'textual>=8,<9' --with pyte python docs/demo/screens.py
"""
import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE.parent

VM = {"default": False, "host": "", "user": "emin", "port": 22, "uri": "qemu:///system", "os": "linux", "dir": "",
      "session": "claude", "autostop": True, "notify": True, "clipboard": True, "idle": 30, "autosnap": 3,
      "created": True, "project": "", "test": "", "yolo": False, "try": "", "net": "open", "cpu_ns": None}
VMS = [
    dict(VM, name="web", default=True, domain="web", agent="claude", agents=["claude", "codex"], ports=[3000, 5173],
         state="running", memory_mb=8192, cpus=4, snapshots=6, project=str(Path.home() / "code/web-app"),
         dir="~/projects/web-app"),
    dict(VM, name="api", domain="api", agent="claude", agents=["claude", "opencode"], ports=[8000], state="running",
         memory_mb=4096, cpus=2, snapshots=3),
    dict(VM, name="ml-lab", domain="ml-lab", agent="claude", agents=["claude", "aider"], ports=[8888],
         state="shut off", memory_mb=16384, cpus=8, snapshots=2),
    dict(VM, name="arch", domain="arch", agent="claude", agents=["claude", "gemini"], ports=[], state="shut off",
         memory_mb=4096, cpus=2, snapshots=3),
    dict(VM, name="lab-pi", domain="", host="192.168.1.40", agent="claude", agents=["claude"], ports=[], state=None,
         memory_mb=None, cpus=None, created=False, snapshots=0),
]
IMAGES = {"images": [{"name": "debian13", "description": "Debian 13 \"trixie\" (default)", "downloaded": True},
                     {"name": "debian12", "description": "Debian 12 \"bookworm\"", "downloaded": True},
                     {"name": "ubuntu24.04", "description": "Ubuntu 24.04 LTS", "downloaded": True},
                     {"name": "arch", "description": "Arch Linux", "downloaded": True}],
          "templates": [],
          "host": {"memory_mb": 32768, "memory_available_mb": 20992, "cpus": 16, "libvirt": True, "pool": "default",
                   "pool_available_gb": 380, "missing": [],
                   "agents": ["claude", "codex", "gemini", "opencode", "aider"]}}

# What the terminal tabs show: Claude Code at work, a shell, OpenCode.
G, D, B, R, X = "\x1b[32m", "\x1b[2m", "\x1b[1m", "\x1b[31m", "\x1b[0m"
CLAUDE = f"""\x1b[38;5;173m╭───────────────────────────────────────────────────╮{X}
\x1b[38;5;173m│{X} \x1b[38;5;173m✻{X} Welcome to {B}Claude Code{X}!                        \x1b[38;5;173m│{X}
\x1b[38;5;173m│{X}   {D}/help for help, /status for your current setup{X}  \x1b[38;5;173m│{X}
\x1b[38;5;173m│{X}   {D}cwd: /home/emin/projects/web-app{X}                \x1b[38;5;173m│{X}
\x1b[38;5;173m╰───────────────────────────────────────────────────╯{X}

{D}>{X} add a /health endpoint that also checks the database

● I'll add the route to src/server.ts and a test for it.

{G}●{X} {B}Update{X}(src/server.ts)
  ⎿  Updated {B}src/server.ts{X} with 9 additions
     41 {G}+ app.get("/health", async (_req, res) => {{{X}
     42 {G}+   try {{{X}
     43 {G}+     await pool.query("select 1");{X}
     44 {G}+     res.json({{ ok: true, db: "up" }});{X}
     45 {G}+   }} catch {{{X}
     46 {G}+     res.status(503).json({{ ok: false, db: "down" }});{X}

{G}●{X} {B}Bash{X}(npm test)
  ⎿  {G}✓{X} test/health.test.ts (2 tests)
     {B}Tests{X}  {G}24 passed{X} (24) in 1.21s

● Done. {B}GET /health{X} answers {{"ok": true, "db": "up"}}, or 503 when the
  database is down; the test is in test/health.test.ts.

{D}╭───────────────────────────────────────────────────────────────╮{X}
{D}│{X} >                                                             {D}│{X}
{D}╰───────────────────────────────────────────────────────────────╯{X}
  {D}? for shortcuts{X}
"""
CHANGES = """Changes on web in ~/projects/web-app (sent: 3f2e1d0):
  b7a9c40 Add a /health endpoint that checks the database
  8d03e1f Work not committed on the VM
 src/server.ts       | 11 +++++++++--
 test/health.test.ts | 22 ++++++++++++++++++++++
 2 files changed, 31 insertions(+), 2 deletions(-)

diff --git a/src/server.ts b/src/server.ts
index 3f2e1d0..9c41b7e 100644
--- a/src/server.ts
+++ b/src/server.ts
@@ -38,8 +38,15 @@ const pool = new Pool({ connectionString: process.env.DATABASE_URL });
 app.use(express.json());
 app.use("/api", routes);

-app.get("/ping", (_req, res) => res.send("pong"));
+app.get("/health", async (_req, res) => {
+  try {
+    await pool.query("select 1");
+    res.json({ ok: true, db: "up" });
+  } catch {
+    res.status(503).json({ ok: false, db: "down" });
+  }
+});

 app.listen(3000, () => console.log("listening on :3000"));
diff --git a/test/health.test.ts b/test/health.test.ts
new file mode 100644
index 0000000..e4d8a2c
"""

FAKE = r'''#!/usr/bin/env python3
import json, os, sys, time
d = os.environ["SHOT_DIR"]
a = sys.argv[1:]
def show(name):
    sys.stdout.write(open(os.path.join(d, name)).read())
if a[:2] == ["list", "--json"]: show("list.json")
elif a[:2] == ["images", "--json"]: show("images.json")
elif a[:1] == ["snapshots"]: print("[]")
elif a[:1] in (["templates"], ["runs"], ["history"]) and "--json" in a: print("[]")
elif a[:1] == ["phone"]: print('{"on": false}')
elif a[:1] == ["update"]: print('{"newer": false}')
elif a[:1] == ["changes"]: show("changes.txt")
elif a[:1] == ["create"]:
    print("Downloading the Ubuntu 24.04 cloud image...", flush=True); time.sleep(3600)
elif a[:1] == ["start"]: print("Started api (snapshot auto-20261018-1402 taken).")
elif a[:1] == ["open"]:
    print("Port 3000 of web: http://localhost:3000"); print("Port 5173 of web: http://localhost:5173")
    print("Stop with Ctrl-C.")
elif "--claude" in a: show("claude.txt"); time.sleep(3600)
elif a[:1] == ["shell"]:
    print("emin@web:~/projects/web-app$ ", end="", flush=True); time.sleep(3600)
elif "--opencode" in a:
    print("\x1b[1mopencode\x1b[0m  api · ~/projects/api", flush=True); time.sleep(3600)
else:
    time.sleep(3600)
'''


def svg_to_png(svg, png):
    """Chromium draws the SVG (its fonts come from the web) at twice the size."""
    text = svg.read_text()
    import re
    m = re.search(r'viewBox="0 0 ([0-9.]+) ([0-9.]+)"', text)
    w, h = int(float(m.group(1))), int(float(m.group(2)))
    html = svg.with_suffix(".html")
    html.write_text(f'<!doctype html><html><body style="margin:0;background:#0c0c0c">{text}</body></html>')
    prof = tempfile.mkdtemp(prefix="chromium-")
    subprocess.run(["chromium", "--headless=new", "--no-first-run", f"--user-data-dir={prof}", "--hide-scrollbars",
                    "--force-device-scale-factor=2", f"--window-size={w},{h}", "--virtual-time-budget=4000",
                    f"--screenshot={png}", html.as_uri()], capture_output=True, timeout=120)
    shutil.rmtree(prof, ignore_errors=True)


async def main():
    d = Path(tempfile.mkdtemp(prefix="vmforai-shots-"))
    (d / "list.json").write_text(json.dumps(VMS))
    (d / "images.json").write_text(json.dumps(IMAGES))
    (d / "changes.txt").write_text(CHANGES)
    (d / "claude.txt").write_text(CLAUDE)
    fake = d / "vmforai"
    fake.write_text(FAKE)
    fake.chmod(0o755)
    os.environ.update(SHOT_DIR=str(d), VMFORAI_BIN=str(fake), VMFORAI_CONF_DIR=str(d / "conf"), LANG="C.UTF-8",
                      XDG_CACHE_HOME=str(d / "cache"))
    s = (ROOT / "vmforai").read_text()
    start = s.index("UI_PY=$(cat <<'UI_END'\n") + len("UI_PY=$(cat <<'UI_END'\n")
    (d / "ui.py").write_text(s[start:s.index("\nUI_END\n", start)])
    spec = importlib.util.spec_from_file_location("vmforai_ui", d / "ui.py")
    ui = importlib.util.module_from_spec(spec)
    os.chdir(d)
    spec.loader.exec_module(ui)
    app = ui.VmforaiUI()
    shots = {}
    async with app.run_test(size=(150, 46)) as pilot:
        for _ in range(50):
            if app.vms and app.info:
                break
            await pilot.pause(0.1)
        # A new VM: the form, filled.
        await pilot.press("n")
        await pilot.pause(0.5)
        form = app.screen
        form.query_one("#name").value = "notebooks"
        form.query_one("#image").value = "ubuntu24.04"
        form.query_one("#memory").value = 16384
        form.query_one("#cpus").value = 8
        form.query_one("#disk").value = "60"
        form.query_one("#agent-codex").value = True
        form.query_one("#agent-aider").value = True
        form.query_one("#ports").value = "8888,6006"
        form.query_one("#idle").value = 60
        await pilot.pause(0.8)
        shots["ui-new"] = app.save_screenshot(path=str(d), filename="ui-new.svg")
        await pilot.press("ctrl+s")  # creating, in a tab of its own
        await pilot.pause(1)
        app.open_session("web", "claude")
        await pilot.pause(1.5)
        app.open_session("web", "shell")
        await pilot.pause(0.5)
        app.open_session("api", "opencode")
        await pilot.pause(1)
        app.action_home()
        await pilot.pause(0.5)
        app.main.query_one("#log").clear()
        app.background(["start", "api"])
        await pilot.pause(0.6)
        app.background(["open", "web", "3000", "5173", "--keep"])
        await pilot.pause(1.2)
        shots["ui"] = app.save_screenshot(path=str(d), filename="ui.svg")
        # Claude Code in its tab.
        terms = app.terminals("web")
        app.show(terms[0].id)
        await pilot.pause(1.5)
        shots["ui-session"] = app.save_screenshot(path=str(d), filename="ui-session.svg")
        # A project's changes.
        app.action_home()
        await pilot.pause(0.3)
        await pilot.press("c")
        await pilot.pause(2)
        shots["ui-changes"] = app.save_screenshot(path=str(d), filename="ui-changes.svg")
        for t in app.terminals():
            t.close()
        for c in app.creating():
            c.cancel()
    for name, svg in shots.items():
        svg_to_png(Path(svg), OUT / f"{name}.png")
        print(OUT / f"{name}.png")
    shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)
