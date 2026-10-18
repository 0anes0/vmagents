"""`vmagents create` / `delete` against fake curl, virsh and virt-install.
A real run on libvirt is described in the README."""
import hashlib
import json
import os
import subprocess

from tests.helpers import SandboxTest, write_exe

IMAGE = b"QFI\xfb fake qcow2 image\n" * 100
DEBIAN = "https://cloud.debian.org/images/cloud/trixie/latest/"

# Fake libvirt: state in $FAKE_LV (JSON: domains, volumes, descriptions).
VIRSH = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args[:1] == ["-c"]: args = args[2:]
path = os.environ["FAKE_LV"]
# One virsh at a time (tries run several), and whole writes only.
import fcntl
lock = open(path + ".lock", "w")
fcntl.flock(lock, fcntl.LOCK_EX)
st = json.load(open(path))
with open(os.environ["STUB_LOG"], "a") as f:
    f.write(json.dumps({"prog": "virsh", "argv": args}) + "\n")
def save():
    json.dump(st, open(path + ".tmp", "w"))
    os.replace(path + ".tmp", path)
def opt(name):
    return args[args.index(name) + 1] if name in args else None
cmd, rest = args[0], [a for a in args[1:] if not a.startswith("--")]
if cmd == "dominfo":
    sys.exit(0 if args[1] in st["domains"] else 1)
if cmd == "pool-dumpxml":
    print("<pool type='dir'>\n  <target>\n    <path>/pool</path>\n  </target>\n</pool>"); sys.exit(0)
if cmd == "vol-info" and "--pool" in args and args[-1] in st["volumes"]:
    print(f"Name:   {args[-1]}\nAllocation:     325.69 MiB"); sys.exit(0)
if cmd == "pool-info" and st.get("nopool"):
    print("error: failed to get pool 'default'", file=sys.stderr); sys.exit(1)
if cmd == "pool-define-as":
    st.pop("nopool", None); save(); sys.exit(0)
if cmd in ("pool-info", "net-info", "net-start", "net-autostart", "pool-refresh", "pool-build", "pool-start",
           "pool-autostart", "uri"):
    sys.exit(0)
if cmd == "vol-info":
    sys.exit(0 if args[-1] in st["volumes"] else 1)
if cmd == "vol-create-as":
    st["volumes"][args[2]] = {"size": args[3], "backing": opt("--backing-vol")}; save(); sys.exit(0)
if cmd == "vol-upload":
    st["volumes"][args[3]]["uploaded"] = open(args[4], "rb").read().decode("latin-1"); save(); sys.exit(0)
if cmd == "vol-delete":
    st["volumes"].pop(args[-1], None); save(); sys.exit(0)
if cmd == "vol-list":
    print(" Name   Path\n------------")
    for k in st["volumes"]: print(f" {k}   /pool/{k}")
    sys.exit(0)
if cmd == "vol-path":
    print(f"/pool/{args[-1]}"); sys.exit(0 if args[-1] in st["volumes"] else 1)
if cmd == "vol-dumpxml":
    b = st["volumes"].get(args[-1], {}).get("backing")
    print("<volume>" + (f"\n  <backingStore>\n    <path>/pool/{b}</path>\n  </backingStore>" if b else "") + "\n</volume>")
    sys.exit(0)
if cmd == "desc":
    print(st["domains"].get(args[1], {}).get("desc", "")); sys.exit(0)
if cmd == "domstate":
    print(st["domains"][args[1]].get("state", "running")); sys.exit(0)
if cmd == "destroy":
    st["domains"][args[1]]["state"] = "shut off"; save(); sys.exit(0)
if cmd == "undefine":
    st["domains"].pop(args[1])
    st["volumes"] = {k: v for k, v in st["volumes"].items() if k not in (args[1] + ".qcow2", args[1] + "-seed.iso")}
    save(); sys.exit(0)
print("unsupported", args, file=sys.stderr); sys.exit(1)
'''

VIRT_INSTALL = r'''#!/usr/bin/env python3
import json, os, re, sys
args = sys.argv[1:]
if args[:2] == ["--osinfo", "list"]:
    print("debian13, debiantrixie\ndebian12, debianbookworm\nlinux2022"); sys.exit(0)
with open(os.environ["STUB_LOG"], "a") as f:
    f.write(json.dumps({"prog": "virt-install", "argv": args}) + "\n")
if os.environ.get("FAIL_INSTALL"):
    print("ERROR boom", file=sys.stderr); sys.exit(1)
path = os.environ["FAKE_LV"]; st = json.load(open(path))
desc = next((a.split("=", 1)[1] for a in args if a.startswith("description=")), "")
st["domains"][args[args.index("--name") + 1]] = {"desc": desc, "state": "running"}
json.dump(st, open(path, "w"))
'''

# Fake ISO tool: the "image" is just the input files, concatenated.
XORRISO = r'''#!/bin/sh
out=; files=; label=
while [ $# -gt 0 ]; do
  case $1 in -o) out=$2; shift 2 ;; -V) label=$2; shift 2 ;; -as|mkisofs|-J|-r) shift ;; *) files="$files $1"; shift ;; esac
done
{ echo "LABEL=$label"; for f in $files; do echo "== ${f##*/}"; cat "$f"; done; } >"$out"
'''

CURL = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
url = args[-1]
with open(os.environ["STUB_LOG"], "a") as f:
    f.write(json.dumps({"prog": "curl", "argv": args}) + "\n")
data = open(os.environ["FAKE_IMAGE"], "rb").read()
if url.endswith("SUMS"):
    h = os.environ.get("FAKE_SUM") or __import__("hashlib").sha512(data).hexdigest()
    sys.stdout.write(f"{h}  debian-13-genericcloud-amd64.qcow2\n0000  debian-13-nocloud-amd64.qcow2\n")
    sys.exit(0)
out = args[args.index("-o") + 1]
open(out, "wb").write(data)
'''


class CreateBase(SandboxTest):
    """A sandbox with fake libvirt, virt-install, curl and xorriso."""
    def setUp(self):
        super().setUp()
        self.lv = self.sb.tmp / "lv.json"
        self.lv.write_text(json.dumps({"domains": {}, "volumes": {}}))
        img = self.sb.tmp / "image"
        img.write_bytes(IMAGE)
        write_exe(self.sb.bin / "virsh", VIRSH)
        write_exe(self.sb.bin / "virt-install", VIRT_INSTALL)
        write_exe(self.sb.bin / "curl", CURL)
        write_exe(self.sb.bin / "xorriso", XORRISO)
        self.sb.env.update({"FAKE_LV": str(self.lv), "FAKE_IMAGE": str(img)})

    def state(self):
        return json.loads(self.lv.read_text())

    def create(self, *args, check=0, env=None):
        return self.sb.run("create", *args, "--no-setup", env=env, check=check)


class CreateTests(CreateBase):
    def test_create(self):
        r = self.create("box", "--memory", "2048", "--cpus", "3", "--disk", "30", "--user", "dev")
        self.assertIn("Created. Next: vmagents setup box", r.stdout)
        key = (self.sb.home / ".ssh" / "vmagents_ed25519.pub").read_text().strip()
        cached = self.sb.home / ".cache" / "vmagents" / "images" / "debian-13-genericcloud-amd64.qcow2"
        self.assertEqual(cached.read_bytes(), IMAGE)
        base = f"vmagents-base-debian13-{hashlib.sha512(IMAGE).hexdigest()[:12]}.qcow2"
        vols = self.state()["volumes"]
        self.assertEqual(vols[base]["uploaded"].encode("latin-1"), IMAGE)
        self.assertEqual(vols["box.qcow2"], {"size": "30G", "backing": base})
        argv = self.sb.calls("virt-install")[-1]["argv"]
        seed = vols["box-seed.iso"]["uploaded"]
        self.assertTrue(seed.startswith("LABEL=cidata\n"), seed)
        self.assertIn("== meta-data\ninstance-id: box-", seed)
        self.assertIn("path: /etc/systemd/networkd.conf.d/50-vmagents.conf", seed)  # copies get their own address
        user_data = seed.split("== user-data\n")[1].split("== ")[0]
        for a, b in [("--memory", "2048"), ("--vcpus", "3"), ("--osinfo", "debian13"),
                     ("--disk", "vol=default/box.qcow2,bus=virtio")]:
            self.assertEqual(argv[argv.index(a) + 1], b)
        self.assertIn("description=created by vmagents", argv)
        # Without a video device the Debian cloud image's GRUB resets in a loop.
        self.assertEqual(argv[argv.index("--video") + 1], "vga")
        self.assertTrue(user_data.startswith("#cloud-config\n"))
        self.assertIn("  - name: dev\n", user_data)
        self.assertIn(f"      - {key}\n", user_data)
        self.assertIn("lock_passwd: true", user_data)
        # The seed is a read-only virtio disk: the Debian 12 cloud kernel has no SATA CD-ROM driver.
        self.assertIn("vol=default/box-seed.iso,device=disk,bus=virtio,readonly=on", argv)
        self.assertNotIn("--cloud-init", argv)
        conf = (self.sb.conf / "hosts" / "box.conf").read_text()
        for line in ("DOMAIN=box", "USER=dev", "OS=linux", "CREATED=1"):
            self.assertIn(line + "\n", conf)

    def test_makes_the_default_pool_when_missing(self):
        # A fresh libvirt on Arch has no "default" storage pool.
        st = self.state(); st["nopool"] = True; self.lv.write_text(json.dumps(st))
        self.assertTrue(json.loads(self.sb.run("images", "--json", check=0).stdout)["host"]["libvirt"])
        r = self.create("a")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("nopool", self.state())
        calls = [c["argv"] for c in self.sb.calls() if c["prog"] == "virsh"]
        self.assertIn(["pool-define-as", "default", "dir", "--target", "/var/lib/libvirt/images"], calls)
        self.assertIn(["pool-autostart", "default"], calls)

    def test_run_from_the_ui_under_uv(self):
        # uv puts a venv python3 without the system modules first in PATH;
        # virt-install (#!/usr/bin/env python3) must not get it.
        venv = self.sb.tmp / "venv"
        write_exe(venv / "python3", "#!/bin/sh\necho 'No module named gi' >&2; exit 1\n")
        path = self.sb.env["PATH"]
        r = self.create("a", env={"PATH": f"{venv}:{path}", "VIRTUAL_ENV": str(venv), "VMAGENTS_HOST_PATH": path})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("a", self.state()["domains"])

    def test_turkish_locale(self):
        # In tr_TR "I" is not in [A-Z]: the profile line DOMAIN=... must still parse.
        env = {"LC_ALL": "tr_TR.UTF-8"}
        if "tr_tr.utf" not in subprocess.run(["locale", "-a"], capture_output=True, text=True).stdout.lower():
            # Not installed: build it here (glibc's localedef needs no root for that).
            loc = self.sb.tmp / "locale"
            loc.mkdir()
            r = subprocess.run(["localedef", "-i", "tr_TR", "-f", "UTF-8", str(loc / "tr_TR.UTF-8")],
                               capture_output=True, text=True)
            if r.returncode not in (0, 1) or not (loc / "tr_TR.UTF-8").is_dir():
                self.skipTest("no tr_TR locale here")
            env["LOCPATH"] = str(loc)
        check = subprocess.run(["bash", "-c", "[[ I =~ ^[A-Z]$ ]]"], env=dict(os.environ, **env))
        self.assertNotEqual(check.returncode, 0, "this locale has I in [A-Z]: the test would prove nothing")
        r = self.create("a", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.sb.run("list", env=env, check=0)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("libvirt:a", r.stdout)

    def test_second_vm_reuses_image_and_base(self):
        self.create("a")
        self.sb.clear_log()
        r = self.create("b")
        self.assertIn("Using base volume vmagents-base-debian13-", r.stderr)
        self.assertEqual([c for c in self.sb.calls("curl") if "-o" in c["argv"]], [])
        uploads = [c["argv"][3] for c in self.sb.calls("virsh") if c["argv"][0] == "vol-upload"]
        self.assertEqual(uploads, ["b-seed.iso"])  # the base volume is not uploaded again

    def test_checksum_mismatch(self):
        r = self.create("box", check=1, env={"FAKE_SUM": "0" * 128})
        self.assertIn("checksum mismatch", r.stderr)
        self.assertEqual(os.listdir(self.sb.home / ".cache" / "vmagents" / "images"), [])
        self.assertFalse((self.sb.conf / "hosts" / "box.conf").exists())

    def test_refuses_existing_names_and_bad_numbers(self):
        st = self.state()
        st["domains"]["win10"] = {"desc": ""}
        self.lv.write_text(json.dumps(st))
        self.assertIn("already has a VM named 'win10'", self.create("win10", check=1).stderr)
        self.assertIn("whole numbers", self.create("x", "--memory", "4G", check=1).stderr)
        self.assertIn("unknown image", self.create("x", "--image", "gentoo", check=1).stderr)
        self.sb.run("add", "taken", "--host", "h", check=0)
        self.assertIn("already exists", self.create("taken", check=1).stderr)

    def test_failed_install_removes_the_disk(self):
        r = self.create("box", check=1, env={"FAIL_INSTALL": "1"})
        self.assertIn("virt-install failed", r.stderr)
        self.assertNotIn("box.qcow2", self.state()["volumes"])
        self.assertNotIn("box-seed.iso", self.state()["volumes"])
        self.assertFalse((self.sb.conf / "hosts" / "box.conf").exists())

    def test_delete(self):
        self.create("box")
        r = self.sb.run("delete", "box")
        self.assertEqual(r.returncode, 1)
        self.assertIn("add --yes", r.stderr)
        self.sb.run("delete", "box", "--yes", check=0)
        self.assertNotIn("box", self.state()["domains"])
        self.assertEqual([v for v in self.state()["volumes"] if v.startswith("box")], [])
        self.assertFalse((self.sb.conf / "hosts" / "box.conf").exists())
        undefine = [c["argv"] for c in self.sb.calls("virsh") if c["argv"][0] == "undefine"]
        self.assertEqual(undefine, [["undefine", "box", "--remove-all-storage", "--snapshots-metadata"]])

    def test_delete_never_touches_other_vms(self):
        st = self.state()
        st["domains"]["win10"] = {"desc": "", "state": "running"}
        self.lv.write_text(json.dumps(st))
        self.sb.run("add", "win10", "--domain", "win10", "--os", "windows", check=0)
        r = self.sb.run("delete", "win10", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("was not created by vmagents", r.stderr)
        # Even a profile claiming CREATED=1 needs libvirt's own marker.
        conf = self.sb.conf / "hosts" / "win10.conf"
        conf.write_text(conf.read_text() + "CREATED=1\n")
        r = self.sb.run("delete", "win10", "--yes")
        self.assertIn("not marked as created by vmagents", r.stderr)
        self.assertIn("win10", self.state()["domains"])
        self.assertEqual(self.state()["domains"]["win10"]["state"], "running")
        self.assertEqual([c for c in self.sb.calls("virsh") if c["argv"][0] in ("destroy", "undefine")], [])


    def test_prune_keeps_bases_in_use(self):
        self.create("a")
        self.create("b")
        self.sb.run("delete", "a", "--yes", check=0)
        r = self.sb.run("prune", check=0)
        self.assertRegex(r.stdout, r"Kept vmagents-base-debian13-\w+\.qcow2 \(a VM uses it\)")
        self.assertIn("Removed downloaded images", r.stdout)
        self.assertFalse((self.sb.home / ".cache" / "vmagents" / "images").exists())
        # The base volume is still there, so a new VM needs no download.
        self.sb.clear_log()
        self.create("c")
        self.assertEqual([c for c in self.sb.calls("curl") if "-o" in c["argv"]], [])
        for name in ("b", "c"):
            self.sb.run("delete", name, "--yes", check=0)
        r = self.sb.run("prune", check=0)
        self.assertRegex(r.stdout, r"Removed vmagents-base-debian13-\w+\.qcow2")
        self.assertEqual(self.state()["volumes"], {})
        self.assertIn("No unused base volumes.", self.sb.run("prune", check=0).stdout)

    def test_images(self):
        r = self.sb.run("images", check=0)
        self.assertRegex(r.stdout, r"debian13 +Debian 13 \"trixie\" \(default\) +- +-\n")
        self.create("a")
        self.create("b")
        r = self.sb.run("images", check=0)
        self.assertRegex(r.stdout, r"debian13 +Debian 13 .* +\S+ +325.69MiB \(a, b\)\n")
        self.assertRegex(r.stdout, r"arch +Arch Linux \(rolling release\) +- +-\n")
        self.assertIn("/pool/vmagents-base-IMAGE-CHECKSUM.qcow2", r.stdout)
        self.assertIn(str(self.sb.home / ".cache" / "vmagents" / "images") + "/", r.stdout)
        self.assertRegex(r.stdout, r"\n      vmagents-base-debian13-\w{12}\.qcow2\n")
