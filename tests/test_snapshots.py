"""Snapshots: one automatically each time vmagents boots a VM, snapshot,
snapshots, undo and autosnap. Against the fake virsh, which keeps snapshots
in a JSON file; the real thing was tried on the Arch and Windows 10 VMs."""
import json

from tests.ptyrun import run_in_pty
from tests.test_stop import Base
from tests.helpers import VMAGENTS


class SnapshotTests(Base):
    def snaps(self):
        path = self.sb.tmp / "virsh.state.snaps"
        return json.loads(path.read_text()) if path.exists() else []

    def set_snaps(self, snaps):
        (self.sb.tmp / "virsh.state.snaps").write_text(json.dumps(snaps))

    def names(self):
        return [s[0] for s in self.snaps()]

    def test_boot_takes_a_snapshot(self):
        self.sb.set_vm("shut off")
        r = self.sb.run("vm", "--keep", check=0)
        self.assertRegex(r.stderr, r"Snapshot auto-\d{8}-\d{6} taken \(\"vmagents undo vm\" goes back to it\)\.")
        cmds = self.virsh_cmds()
        self.assertLess(cmds.index("snapshot-create-as"), cmds.index("start"))
        self.assertEqual(self.snaps()[0][2:], ["shutoff", "taken by vmagents before starting the VM"])

    def test_running_vm_gets_none(self):
        self.sb.run("vm", "--keep", check=0)
        self.assertEqual(self.snaps(), [])

    def test_keeps_the_newest_automatic_ones(self):
        old = [[f"auto-2026010{i}-000000", f"2026-01-0{i} 00:00:00 +0300", "shutoff", ""] for i in range(1, 5)]
        self.set_snaps(old[:2] + [["mine", "2026-01-02 12:00:00 +0300", "running", "before upgrade"]] + old[2:])
        self.sb.set_vm("shut off")
        self.sb.run("vm", "--keep", check=0)
        names = self.names()
        self.assertIn("mine", names)  # never pruned
        autos = [n for n in names if n.startswith("auto-")]
        self.assertEqual(len(autos), 3)
        self.assertNotIn("auto-20260101-000000", autos)
        self.assertNotIn("auto-20260102-000000", autos)

    def test_autosnap(self):
        self.assertIn("newest 5 are kept", self.sb.run("autosnap", "vm", "5", check=0).stdout)
        self.assertIn("AUTOSNAP=5\n", self.profile())
        self.assertIn("are off", self.sb.run("autosnap", "vm", "off", check=0).stdout)
        self.assertIn("AUTOSNAP=0\n", self.profile())
        self.sb.set_vm("shut off")
        self.sb.run("vm", "--keep", check=0)
        self.assertEqual(self.snaps(), [])
        self.sb.run("autosnap", "vm", "on", check=0)
        self.assertIn("AUTOSNAP=3\n", self.profile())
        self.assertEqual(self.sb.run("autosnap", "vm", "some").returncode, 2)
        self.sb.run("add", "h", "--host", "192.0.2.1", check=0)
        self.assertIn("needs a libvirt VM", self.sb.run("autosnap", "h", "on").stderr)

    def test_failed_snapshot_still_starts(self):
        self.sb.set_vm("shut off")
        r = self.sb.run("vm", "--keep", env={"STUB_VIRSH_SNAPSHOT_FAILS": "1"}, check=0)
        self.assertIn("warning: no automatic snapshot: error: internal snapshots", r.stderr)
        self.assertIn("vmagents autosnap vm off", r.stderr)
        self.assertIn("start", self.virsh_cmds())

    def test_snapshot_and_list(self):
        self.assertIn("No snapshots of vm yet", self.sb.run("snapshots", "vm", check=0).stdout)
        r = self.sb.run("snapshot", "vm", "before the refactor", check=0)
        self.assertIn("its memory is saved too", r.stderr)  # the VM is running
        self.assertRegex(r.stdout, r"Snapshot (snap-\d{8}-\d{6}) taken\. Back to it later: vmagents undo vm snap-")
        snap = self.names()[0]
        out = self.sb.run("snapshots", "vm", check=0).stdout
        self.assertRegex(out, rf"{snap}\s+2026-10-16 10:00:00\s+VM running\s+before the refactor")
        self.assertIn(f"Deleted snapshot {snap}.", self.sb.run("snapshot", "vm", "--delete", snap, check=0).stdout)
        self.assertEqual(self.snaps(), [])
        self.assertEqual(self.sb.run("snapshot", "vm", "--delete", "nope").returncode, 1)

    def test_undo(self):
        r = self.sb.run("undo", "vm", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no snapshots of vm yet", r.stderr)
        self.set_snaps([["auto-1", "2026-10-16 09:00:00 +0300", "shutoff", ""],
                        ["auto-2", "2026-10-16 10:00:00 +0300", "shutoff", ""]])
        r = self.sb.run("undo", "vm")
        self.assertEqual(r.returncode, 1)
        self.assertIn("add --yes to confirm without a terminal", r.stderr)
        self.sb.clear_log()
        r = self.sb.run("undo", "vm", "--yes", check=0)
        self.assertIn("VM vm is back at auto-2 (2026-10-16 10:00:00).", r.stdout)
        self.assertIn("Open Claude in it again: vmagents vm", r.stdout)
        cmds = self.virsh_cmds()
        self.assertLess(cmds.index("destroy"), cmds.index("snapshot-revert"))  # was running
        self.assertEqual(self.sb.calls("virsh")[-1]["argv"][2:], ["snapshot-revert", "testvm", "auto-2"])
        self.assertEqual(self.state(), "shut off")
        r = self.sb.run("undo", "vm", "auto-1", "--yes", check=0)
        self.assertIn("back at auto-1", r.stdout)
        self.assertIn("no snapshot 'x' of vm", self.sb.run("undo", "vm", "x", "--yes").stderr)

    def test_undo_to_a_running_snapshot(self):
        self.set_snaps([["snap-1", "2026-10-16 09:00:00 +0300", "running", "live"]])
        self.sb.set_vm("shut off")
        r = self.sb.run("undo", "vm", "--yes", check=0)
        self.assertNotIn("destroy", self.virsh_cmds())
        self.assertNotIn("Open Claude", r.stdout)
        self.assertEqual(self.state(), "running")

    def test_undo_asks(self):
        self.set_snaps([["auto-1", "2026-10-16 09:00:00 +0300", "shutoff", ""]])
        out = run_in_pty([str(VMAGENTS), "undo", "vm"], self.sb.env, str(self.sb.tmp), answers=[("[y/N] ", "n\r")])
        self.assertIn("Everything changed in the VM since then is lost", out)
        self.assertIn("nothing changed", out)
        self.assertNotIn("snapshot-revert", self.virsh_cmds())
        out = run_in_pty([str(VMAGENTS), "undo", "vm"], self.sb.env, str(self.sb.tmp), answers=[("[y/N] ", "y\r")])
        self.assertIn("VM vm is back at auto-1", out)

    def test_doctor_counts_snapshots(self):
        self.set_snaps([["auto-1", "2026-10-16 09:00:00 +0300", "shutoff", ""]])
        r = self.sb.run("doctor", "vm", env={"STUB_SSH_OUTPUT": "claude=1.0\nidle=30 active\nhooks=on\n"})
        self.assertIn("info  snapshots: 1, newest auto-1", r.stdout)
        self.assertIn("ok    idle shutdown: after 30 minutes without use", r.stdout)
        self.assertIn("ok    Claude hooks (idle state, notifications): installed", r.stdout)

    def test_names_and_labels(self):
        r = self.sb.run("snapshot", "vm", "--name", "clean-install", "fresh & <new>", check=0)
        self.assertIn("Snapshot clean-install taken.", r.stdout)
        self.assertEqual(self.snaps()[0][0], "clean-install")
        self.assertIn("already has a snapshot named clean-install",
                      self.sb.run("snapshot", "vm", "--name", "clean-install").stderr)
        self.assertIn("names starting with auto- are for automatic snapshots",
                      self.sb.run("snapshot", "vm", "--name", "auto-1").stderr)
        self.assertIn("letters, digits", self.sb.run("snapshot", "vm", "--name", "a b").stderr)
        snaps = json.loads(self.sb.run("snapshots", "vm", "--json", check=0).stdout)
        self.assertEqual(snaps[0]["description"], "fresh & <new>")
        self.sb.run("snapshot", "vm", "--label", "clean-install", "worked: ü & <ok>", check=0)
        self.assertEqual(self.snaps()[0][3], "worked: ü & <ok>")
        self.sb.run("snapshot", "vm", "--label", "clean-install", "", check=0)
        snaps = json.loads(self.sb.run("snapshots", "vm", "--json", check=0).stdout)
        self.assertEqual(snaps[0]["description"], "")  # not the VM's own description
        self.assertEqual(self.sb.run("snapshot", "vm", "--label", "nope", "x").returncode, 1)
