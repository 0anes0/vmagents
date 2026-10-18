"""Tries: copies of a VM made with vol-clone and a new libvirt definition,
each given the same task (try), listed (tries) and deleted (try --clean).
Against a fake libvirt that keeps domains, their XML and volumes."""
import json
import re
import shutil
import subprocess
import time

from tests.helpers import listening_port, write_exe
from tests.test_create import VIRSH, CreateBase
from tests.test_runs import CLAUDE, TMUX

# The create tests' fake libvirt, plus what copying a VM needs.
VIRSH_TRY = VIRSH.replace('print("unsupported", args, file=sys.stderr); sys.exit(1)', r'''
import re
def dom(n):
    if n not in st["domains"]:
        print(f"error: failed to get domain '{n}'", file=sys.stderr); sys.exit(1)
    return st["domains"][n]
if cmd == "dumpxml":
    d = dom(rest[0])
    disks = "".join(f"    <disk type='file' device='disk'>\n      <source file='{p}'/>\n      <target dev='{t}'/>\n"
                    f"    </disk>\n" for t, p in d.get("disks", {}).items())
    print(f"<domain type='kvm'>\n  <name>{rest[0]}</name>\n  <uuid>0000-{rest[0]}</uuid>\n"
          f"  <description>{d.get('desc', '')}</description>\n"
          f"  <memory unit='KiB'>{d.get('kib', 4194304)}</memory>\n"
          f"  <currentMemory unit='KiB'>{d.get('kib', 4194304)}</currentMemory>\n  <devices>\n{disks}"
          f"    <interface type='network'>\n      <mac address='52:54:00:00:00:01'/>\n    </interface>\n"
          f"  </devices>\n</domain>")
    sys.exit(0)
if cmd == "domblklist":
    print(" Type   Device   Target   Source\n--------------------------------")
    for t, p in dom(rest[0]).get("disks", {}).items():
        print(f" file   disk     {t}      {p}")
    sys.exit(0)
if cmd == "vol-pool":
    print("default"); sys.exit(0)
if cmd == "vol-clone":
    st["volumes"][rest[-1]] = dict(st["volumes"][rest[-2]]); save(); sys.exit(0)
if cmd == "define":
    x = open(rest[0]).read()
    name = re.search(r"<name>(.*?)</name>", x).group(1)
    st["domains"][name] = {"desc": re.search(r"<description>(.*?)</description>", x).group(1), "state": "shut off",
                           "kib": int(re.search(r"<memory unit='KiB'>(\d+)<", x).group(1)),
                           "disks": {t: p for p, t in re.findall(r"<source file='([^']*)'/>\s*<target dev='(\w+)'", x)},
                           "xml": x}
    save(); sys.exit(0)
if cmd == "start":
    dom(rest[0])["state"] = "running"; save(); sys.exit(0)
if cmd == "shutdown":
    dom(rest[0])["state"] = "shut off"; save(); sys.exit(0)
if cmd == "domifaddr":
    print(" Name   MAC address   Protocol   Address\n-----------------------------------------")
    if dom(rest[0]).get("state", "running") == "running":
        print(" vnet0  52:54:00:00:00:02  ipv4  127.0.0.1/24")
    sys.exit(0)
if cmd == "domiflist":
    print(" Interface   Type      Source    Model    MAC\n---------------------------------------------")
    if dom(rest[0]).get("mac"):
        print(f" vnet0       network   default   virtio   {dom(rest[0])['mac']}")
    sys.exit(0)
if cmd == "net-dhcp-leases":
    print(" Expiry Time   MAC address   Protocol   IP address   Hostname   Client ID or DUID\n" + "-" * 60)
    st["lease_asks"] = st.get("lease_asks", 0) + 1
    if st.get("later_leases") and st["lease_asks"] > 2:  # its new address comes a little later
        st["leases"] = st.pop("later_leases")
    save()
    for l in st.get("leases", []):
        if l[1] == opt("--mac"):
            print(f" {l[0]}   {l[1]}   ipv4   {l[2]}/24   -   01:02")
    sys.exit(0)
if cmd in ("snapshot-list", "snapshot-create-as"):
    sys.exit(0)
print("unsupported", args, file=sys.stderr); sys.exit(1)
''').replace('''if cmd == "dominfo":
    sys.exit(0 if args[1] in st["domains"] else 1)''', '''if cmd == "dominfo":
    if args[1] not in st["domains"]:
        sys.exit(1)
    print(f"Name: {args[1]}\\nMax memory:     {st['domains'][args[1]].get('kib', 4194304)} KiB"); sys.exit(0)''').replace(
    '''if cmd == "desc":
    print(st["domains"].get(args[1], {}).get("desc", "")); sys.exit(0)''', '''if cmd == "desc":
    if len(rest) > 1:
        st["domains"][rest[0]]["desc"] = rest[-1]; save(); sys.exit(0)
    print(st["domains"].get(args[1], {}).get("desc", "")); sys.exit(0)''')


class TryTests(CreateBase):
    def setUp(self):
        super().setUp()
        write_exe(self.sb.bin / "virsh", VIRSH_TRY)
        self.listener, self.port = listening_port()
        self.addCleanup(self.listener.close)
        self.lv.write_text(json.dumps({
            "domains": {"src": {"desc": "created by vmagents", "state": "shut off", "kib": 2097152,
                                "disks": {"vda": "/pool/src.qcow2", "vdb": "/pool/src-seed.iso"}}},
            "volumes": {"src.qcow2": {"backing": "vmagents-base-debian13.qcow2"}, "src-seed.iso": {}}}))
        self.sb.run("add", "src", "--domain", "src", "--port", str(self.port), "--os", "linux", check=0)
        with open(self.sb.conf / "hosts" / "src.conf", "a") as f:
            f.write("CREATED=1\nAGENTS=claude,codex\n")
        self.sb.env["STUB_SSH_HOSTNAME_FROM_ALIAS"] = "1"
        (self.sb.conf / "known_hosts").write_text("vmagents-src ssh-ed25519 AAAAkey\nvmagents-src-t1 ssh-ed25519 OLD\n")
        key = self.sb.home / ".ssh" / "vmagents_ed25519"
        key.parent.mkdir(parents=True, exist_ok=True)
        key.write_text("private")
        key.with_suffix(".pub").write_text("ssh-ed25519 AAAApub me@here")

    def profile(self, name):
        return (self.sb.conf / "hosts" / f"{name}.conf").read_text()

    def test_copies(self):
        r = self.sb.run("try", "src", "2", check=0)
        self.assertIn("Made 2 copies of src: src-t1 src-t2", r.stdout)
        st = self.state()
        for n in ("src-t1", "src-t2"):
            d = st["domains"][n]
            self.assertEqual(d["state"], "running")
            self.assertEqual(d["desc"], "created by vmagents (try of src)")
            self.assertEqual(d["disks"], {"vda": f"/pool/{n}.qcow2", "vdb": f"/pool/{n}-seed.iso"})
            self.assertNotIn("<uuid>", d["xml"])  # libvirt makes new ones
            self.assertNotIn("<mac address", d["xml"])
            self.assertEqual(st["volumes"][f"{n}.qcow2"], {"backing": "vmagents-base-debian13.qcow2"})
            # Its own cloud-init seed: a new instance (new network settings and host keys), named after it.
            seed = st["volumes"][f"{n}-seed.iso"]["uploaded"]
            self.assertIn(f"instance-id: {n}-", seed)
            self.assertIn(f"hostname: {n}\n", seed)
            self.assertIn("ssh-ed25519 AAAApub me@here", seed)
            self.assertNotIn("packages:", seed)
            self.assertIn("[cloud-init-per, instance, vmagents-copy, sh, -c, \"rm -f /etc/machine-id", seed)
            self.assertIn("DUIDType=link-layer", seed)
            self.assertNotIn("network-config", seed)
            p = self.profile(n)
            for line in (f"DOMAIN={n}", "TRY=src", "AUTOSNAP=0", "CREATED=1", "AGENT=claude"):
                self.assertIn(line + "\n", p)
            self.assertNotIn(f"vmagents-{n} ", (self.sb.conf / "known_hosts").read_text())  # new host keys
        self.assertEqual(st["domains"]["src"]["state"], "shut off")
        # Started one after the other, each checked by its hostname, without keeping its first host key.
        checks = [c["argv"] for c in self.sb.calls("ssh") if "cloud-init status --wait" in c["argv"][-1]]
        self.assertEqual([next(a for a in c if a.startswith("HostKeyAlias=")) for c in checks],
                         ["HostKeyAlias=vmagents-src-t1", "HostKeyAlias=vmagents-src-t2"])
        self.assertIn("UserKnownHostsFile=/dev/null", checks[0][:4])
        self.assertIn("Made 1 copies of src: src-t3", self.sb.run("try", "src", "1", check=0).stdout)  # the next free
        out = self.sb.run("tries", "src", check=0).stdout
        self.assertRegex(out, r"src-t1 +running +Claude Code")
        self.assertIn("src-t3", out)
        self.assertIn("Deleted the tries of src", self.sb.run("try", "src", "--clean", check=0).stdout)
        st = self.state()
        self.assertEqual(sorted(st["domains"]), ["src"])
        self.assertEqual(sorted(st["volumes"]), ["src-seed.iso", "src.qcow2"])
        self.assertFalse((self.sb.conf / "hosts" / "src-t1.conf").exists())
        self.assertIn("src has no tries", self.sb.run("tries", "src", check=0).stdout)

    def test_the_newest_lease_wins(self):
        # A copy's first lease (the old DHCP identity) can outlive its address.
        st = self.state()
        st["domains"]["src"].update(state="running", mac="52:54:00:00:00:09")
        st["leases"] = [["2026-10-18 18:02:10", "52:54:00:00:00:09", "192.0.2.25"],
                        ["2026-10-18 18:00:07", "52:54:00:00:00:09", "192.0.2.46"],
                        ["2026-10-18 18:09:00", "52:54:00:00:00:77", "192.0.2.99"]]
        self.lv.write_text(json.dumps(st))
        r = self.sb.run("shell", "src", "true", env={"VMAGENTS_BOOT_TIMEOUT": "1"})
        self.assertIn("on 192.0.2.25:", r.stderr)  # not the old .46

    def test_a_new_address_while_it_boots(self):
        st = self.state()
        st["domains"]["src"].update(state="running", mac="52:54:00:00:00:09")
        st["leases"] = [["2026-10-18 18:00:07", "52:54:00:00:00:09", "192.0.2.46"]]  # old: nobody answers there
        st["later_leases"] = [["2026-10-18 18:09:00", "52:54:00:00:00:09", "127.0.0.1"]]
        self.lv.write_text(json.dumps(st))
        r = self.sb.run("start", "src", env={"VMAGENTS_BOOT_TIMEOUT": "40"}, check=0)
        self.assertIn("Waiting for SSH on 192.0.2.46:", r.stderr)
        self.assertIn("Its address is 127.0.0.1 now.", r.stderr)
        self.assertIn("VM src is running: ", r.stdout)

    def test_memory_and_checks(self):
        self.sb.run("try", "src", "1", "--memory", "1024", check=0)
        self.assertEqual(self.state()["domains"]["src-t1"]["kib"], 1048576)
        r = self.sb.run("try", "src", "9", "--memory", "100000000")
        self.assertIn("9 copies need 900000000 MB of memory", r.stderr)
        self.assertEqual(self.sb.run("try", "src").returncode, 2)  # how many?
        self.assertIn("is itself a try of src", self.sb.run("try", "src-t1", "2").stderr)
        self.assertIn("--agents takes", self.sb.run("try", "src", "2", "--agents", "copilot").stderr)
        st = self.state()
        st["domains"]["src"]["state"] = "running"
        self.lv.write_text(json.dumps(st))
        self.assertIn("src is running", self.sb.run("try", "src", "1").stderr)
        self.sb.run("add", "other", "--domain", "src", check=0)
        self.assertIn("made with \"vmagents create\" only", self.sb.run("try", "other", "1").stderr)
        for cmd in ("try", "tries"):
            self.assertIn(f"vmagents {cmd} NAME", self.sb.run("help", cmd, check=0).stdout)

    def test_stop_first(self):
        st = self.state()
        st["domains"]["src"]["state"] = "running"
        self.lv.write_text(json.dumps(st))
        r = self.sb.run("try", "src", "1", "--stop", check=0)
        self.assertIn("Shutting src down first", r.stderr)
        self.assertEqual(self.state()["domains"]["src"]["state"], "shut off")

    def test_a_task_in_each_copy(self):
        rb = self.sb.remote_bin
        for tool in ("mktemp", "pwd", "sort", "kill", "python3", "tail", "readlink", "git"):
            if shutil.which(tool) and not (rb / tool).exists():
                (rb / tool).symlink_to(shutil.which(tool))
        write_exe(rb / "tmux", TMUX)
        write_exe(rb / "claude", CLAUDE)
        write_exe(rb / "codex", "#!/bin/sh\necho \"codex $*\" >>\"$HOME/agent-args\"\n")
        # The project: copied as the source had it.
        repo = self.sb.tmp / "app"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-q",
                        "--allow-empty", "-m", "one"], check=True)
        subprocess.run(["git", "-C", str(repo), "update-ref", "refs/vmagents/src/base", "HEAD"], check=True)
        with open(self.sb.conf / "hosts" / "src.conf", "a") as f:
            f.write(f"PROJECT={repo}\n")
        env = {"STUB_SSH_EXEC": "1", "DISPLAY": "", "VMAGENTS_WATCH_INTERVAL": "0.2"}
        r = self.sb.run("try", "src", "2", "--agents", "claude,codex", "--", "make it faster", env=env, check=0)
        self.assertIn("Run 1 on src-t1: Claude Code works on it", r.stdout)
        self.assertIn("Run 2 on src-t2: Codex works on it", r.stdout)
        self.assertIn("src-t1 shuts down when it is done", r.stdout)
        self.assertIn("AGENT=codex\n", self.profile("src-t2"))
        args = (self.sb.remote_home / "agent-args").read_text()
        self.assertIn("--dangerously-skip-permissions make it faster", args)
        for _ in range(600):  # each copy shuts down when its task is done
            st = self.state()
            if all(st["domains"][n]["state"] == "shut off" for n in ("src-t1", "src-t2")):
                break
            time.sleep(0.05)
        self.assertEqual([self.state()["domains"][n]["state"] for n in ("src-t1", "src-t2")], ["shut off"] * 2)
        self.assertIn("codex exec --skip-git-repo-check", (self.sb.remote_home / "agent-args").read_text())
        refs = subprocess.run(["git", "-C", str(repo), "for-each-ref", "--format=%(refname)", "refs/vmagents/"],
                              capture_output=True, text=True).stdout.split()
        self.assertEqual(refs, ["refs/vmagents/src-t1/base", "refs/vmagents/src-t2/base", "refs/vmagents/src/base"])
        self.sb.run("try", "src", "--clean", check=0)
        refs = subprocess.run(["git", "-C", str(repo), "for-each-ref", "--format=%(refname)", "refs/vmagents/"],
                              capture_output=True, text=True).stdout.split()
        self.assertEqual(refs, ["refs/vmagents/src/base"])
        self.assertTrue(re.search(r"PROJECT=", self.profile("src")))
