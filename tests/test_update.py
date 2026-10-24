"""update: vmagents puts itself at its latest release. Against a fake GitHub
(a fake curl that answers from a folder), on a copy of the script."""
import hashlib
import json
import shutil
import subprocess

from tests.helpers import VMAGENTS, SandboxTest, write_exe

BASE = "https://example.test/vmagents"
RAW = "https://raw.example.test/vmagents"

# curl as update uses it: the latest release's page (-w %{url_effective}) and
# downloads (-o FILE), from $FAKE_GH; a path that is not there fails.
CURL = r'''#!/usr/bin/env python3
import os, sys
a = sys.argv[1:]
url = a[-1]
d = os.environ["FAKE_GH"]
with open(os.path.join(d, "calls"), "a") as f:
    f.write(url + "\n")
if url.endswith("/releases/latest"):
    print(open(os.path.join(d, "latest-url")).read().strip(), end="")
    sys.exit(0)
path = os.path.join(d, url.split("://", 1)[1].replace("/", "_"))
if not os.path.exists(path):
    print("curl: (22) 404", file=sys.stderr)
    sys.exit(22)
data = open(path, "rb").read()
if "-o" in a:
    open(a[a.index("-o") + 1], "wb").write(data)
else:
    sys.stdout.buffer.write(data)
'''


class UpdateTests(SandboxTest):
    def setUp(self):
        super().setUp()
        self.gh = self.sb.tmp / "gh"
        self.gh.mkdir()
        write_exe(self.sb.bin / "curl", CURL)
        self.sb.env.update(FAKE_GH=str(self.gh), VMAGENTS_UPDATE_URL=BASE, VMAGENTS_UPDATE_RAW=RAW)
        self.installed = self.sb.tmp / "inst" / "bin" / "vmagents"
        self.installed.parent.mkdir(parents=True)
        shutil.copy(VMAGENTS, self.installed)
        self.current = self.version(self.installed)
        self.new = VMAGENTS.read_text().replace(f"\nVERSION={self.current}\n", "\nVERSION=9.9.9\n", 1)
        self.release("9.9.9", self.new)

    def version(self, path):
        return subprocess.run([str(path), "--version"], capture_output=True, text=True).stdout.split()[-1]

    def put(self, url, data):
        (self.gh / url.split("://", 1)[1].replace("/", "_")).write_bytes(data.encode() if isinstance(data, str) else data)

    def release(self, v, script, sums=True, asset=True):
        (self.gh / "latest-url").write_text(f"{BASE}/releases/tag/v{v}")
        if asset:
            self.put(f"{BASE}/releases/download/v{v}/vmagents", script)
        else:
            self.put(f"{RAW}/v{v}/vmagents", script)
        if sums:
            digest = hashlib.sha256(script.encode()).hexdigest()
            self.put(f"{BASE}/releases/download/v{v}/SHA256SUMS", f"{digest}  vmagents\n{'0' * 64}  vmagents_{v}_all.deb\n")

    def update(self, *args, **kw):
        e = dict(self.sb.env, **kw.pop("env", {}))
        return subprocess.run([str(self.installed), "update", *args], env=e, cwd=self.sb.tmp, capture_output=True,
                              text=True, stdin=subprocess.DEVNULL, timeout=60)

    def test_check_then_update(self):
        r = self.update("--check")
        self.assertIn(f"vmagents 9.9.9 is out (this is {self.current})", r.stdout)
        self.assertIn("Update: vmagents update", r.stdout)
        self.assertEqual(self.version(self.installed), self.current)
        info = json.loads(self.update("--json").stdout)
        self.assertEqual(info, {"current": self.current, "latest": "9.9.9", "newer": True})
        r = self.update()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Updated: vmagents 9.9.9.", r.stdout)
        self.assertEqual(self.version(self.installed), "9.9.9")
        self.assertEqual(oct(self.installed.stat().st_mode & 0o777), "0o755")
        self.assertEqual([p.name for p in self.installed.parent.iterdir()], ["vmagents"])  # nothing left over
        r = self.update()
        self.assertIn("vmagents 9.9.9 is the latest.", r.stdout)

    def test_checksum_and_contents_are_checked(self):
        self.put(f"{BASE}/releases/download/v9.9.9/SHA256SUMS", f"{'1' * 64}  vmagents\n")
        r = self.update()
        self.assertEqual(r.returncode, 1)
        self.assertIn("its checksum differs", r.stderr)
        self.assertEqual(self.version(self.installed), self.current)
        self.release("9.9.9", "<html>not found</html>\n")
        r = self.update()
        self.assertIn("is not vmagents 9.9.9", r.stderr)
        self.assertEqual(self.version(self.installed), self.current)
        self.assertEqual(len(list(self.installed.parent.iterdir())), 1)

    def test_older_release_without_assets(self):
        # Releases before 0.23.0 have no script or SHA256SUMS: the tag's file then.
        for f in self.gh.iterdir():
            if f.name != "latest-url":
                f.unlink()
        self.release("9.9.9", self.new, sums=False, asset=False)
        r = self.update()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.version(self.installed), "9.9.9")

    def test_not_newer(self):
        self.release("0.0.1", self.new)
        self.assertIn(f"vmagents {self.current} is the latest.", self.update().stdout)
        self.assertFalse(json.loads(self.update("--json").stdout)["newer"])

    def test_cached_check(self):
        self.update("--json", "--cached")
        self.update("--json", "--cached")
        calls = (self.gh / "calls").read_text().splitlines()
        self.assertEqual(calls.count(f"{BASE}/releases/latest"), 1)  # the second one from the cache

    def test_offline(self):
        (self.gh / "latest-url").write_text("https://example.test/vmagents/releases")
        r = self.update()
        self.assertEqual(r.returncode, 1)
        self.assertIn("could not find the latest version", r.stderr)

    def test_git_checkout(self):
        e = dict(self.sb.env)
        r = subprocess.run([str(VMAGENTS), "update"], env=e, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn("runs from a git checkout", r.stderr)

    def test_help(self):
        self.assertIn("vmagents update [--check]", self.sb.run("help", "update", check=0).stdout)
