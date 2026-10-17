"""vmagents mount / umount with a fake sshfs and fusermount, which record
"mounts" in a file standing in for /proc/mounts."""
import os

from tests.helpers import SandboxTest, write_exe

SSHFS = r'''#!/bin/sh
printf '%s\n' "$@" >"$STUB_SSHFS_ARGS"
[ -n "$STUB_SSHFS_FAIL" ] && { echo "read: Connection reset by peer" >&2; exit 1; }
for last; do :; done
echo "sshfs#remote $(readlink -f "$last") fuse.sshfs rw 0 0" >>"$VMAGENTS_MOUNTS_FILE"
'''
FUSERMOUNT = r'''#!/bin/sh
d=$(readlink -f "$2")
grep -v " $d " "$VMAGENTS_MOUNTS_FILE" >"$VMAGENTS_MOUNTS_FILE.new"; mv "$VMAGENTS_MOUNTS_FILE.new" "$VMAGENTS_MOUNTS_FILE"
'''


class MountTests(SandboxTest):
    def setUp(self):
        super().setUp()
        self.sb.run("add", "vm", "--host", "192.0.2.7", "--user", "dev", "--port", "2222", "--os", "linux",
                    "--dir", "~/work", check=0)
        self.mounts = self.sb.tmp / "mounts"
        self.mounts.write_text("")
        self.args = self.sb.tmp / "sshfs.args"
        write_exe(self.sb.bin / "sshfs", SSHFS)
        write_exe(self.sb.bin / "fusermount3", FUSERMOUNT)
        self.sb.env.update({"VMAGENTS_MOUNTS_FILE": str(self.mounts), "STUB_SSHFS_ARGS": str(self.args),
                            "STUB_SSH_EXEC": "1"})
        self.mp = self.sb.home / "vm" / "vm"

    def test_mount_and_umount(self):
        r = self.sb.run("mount", "vm", check=0)
        work = self.sb.remote_home / "work"
        self.assertIn(f"Mounted vm:{work} at {self.mp}", r.stdout)
        self.assertIn("still run on THIS computer", r.stdout)
        args = self.args.read_text().splitlines()
        self.assertEqual(args[-2:], [f"dev@192.0.2.7:{work}", str(self.mp)])
        opts = ",".join(a for a in args if a != "-o")
        for o in ("Port=2222", "HostKeyAlias=vmagents-vm", "BatchMode=yes", "reconnect", "idmap=user",
                  f"UserKnownHostsFile={self.sb.conf}/known_hosts"):
            self.assertIn(o, opts)
        self.assertIn("Already mounted", self.sb.run("mount", "vm", check=0).stdout)
        self.assertIn(f"Unmounted {self.mp}", self.sb.run("umount", "vm", check=0).stdout)
        self.assertFalse(self.mp.exists())
        self.assertIn("Not mounted", self.sb.run("umount", "vm", check=0).stdout)

    def test_custom_folder_must_be_empty(self):
        d = self.sb.tmp / "here"
        d.mkdir()
        (d / "x").write_text("x")
        r = self.sb.run("mount", "vm", str(d))
        self.assertEqual(r.returncode, 1)
        self.assertIn("is not empty", r.stderr)
        os.remove(d / "x")
        self.sb.run("mount", "vm", str(d), check=0)
        self.assertEqual(self.args.read_text().splitlines()[-1], str(d))

    def test_failures(self):
        r = self.sb.run("mount", "vm", env={"STUB_SSHFS_FAIL": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("sshfs failed: read: Connection reset by peer", r.stderr)
        self.assertFalse(self.mp.exists())  # the empty folder it made is gone again

    def test_windows_paths(self):
        self.sb.run("add", "vm", "--os", "windows", check=0)
        out = "os=windows\r\nhome=C:\\Users\\dev\r\ndir=C:\\Users\\dev\\work\r\n"
        self.sb.run("mount", "vm", env={"STUB_SSH_EXEC": "", "STUB_SSH_OUTPUT": out}, check=0)
        self.assertEqual(self.args.read_text().splitlines()[-2], "dev@192.0.2.7:/C:/Users/dev/work")
