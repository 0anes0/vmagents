import subprocess
import unittest
from pathlib import Path

from tests.helpers import ROOT, SandboxTest


class InstallTests(SandboxTest):
    def install(self, *args):
        env = dict(self.sb.env, PATH="/usr/bin:/bin")
        return subprocess.run([str(ROOT / "install.sh"), *args], env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True)

    def test_install_and_uninstall(self):
        prefix = self.sb.tmp / "prefix"
        r = self.install("--prefix", str(prefix))
        self.assertEqual(r.returncode, 0, r.stderr)
        binary = prefix / "bin" / "vmagents"
        self.assertEqual(binary.read_bytes(), (ROOT / "vmagents").read_bytes())
        self.assertTrue(binary.stat().st_mode & 0o111)
        self.assertIn("is now on the PATH in ~/.bashrc: open a new terminal", r.stdout)
        bashrc = self.sb.home / ".bashrc"
        self.assertIn(f'export PATH="{prefix}/bin:$PATH"  # vmagents\n', bashrc.read_text())
        self.install("--prefix", str(prefix))  # again: not twice
        self.assertEqual(bashrc.read_text().count("# vmagents"), 1)
        r = self.install("--prefix", str(prefix), "--uninstall")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(binary.exists())
        self.assertNotIn("vmagents", bashrc.read_text())
        r = self.install("--prefix", str(prefix), "--no-modify-path")
        self.assertIn("is not on your PATH", r.stdout)
        self.assertNotIn("vmagents", bashrc.read_text())

    def test_installs_what_it_uses(self):
        # By default install.sh then runs "vmagents deps --yes"; a fake sudo stands in for the real one.
        log = self.sb.tmp / "sudo.log"
        fake = self.sb.tmp / "fakebin"
        fake.mkdir()
        (fake / "sudo").write_text(f'#!/bin/sh\necho "$*" >>"{log}"\nexit 1\n')
        (fake / "sudo").chmod(0o755)
        (fake / "curl").write_text(f'#!/bin/sh\necho "curl $*" >>"{log}"\nexit 1\n')  # (no uv from the internet)
        (fake / "curl").chmod(0o755)
        env = dict(self.sb.env, PATH=f"{fake}:/usr/bin:/bin")
        env.pop("VMAGENTS_NO_DEPS")
        r = subprocess.run([str(ROOT / "install.sh"), "--prefix", str(self.sb.tmp / "p")], env=env,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("What vmagents uses on this computer:", r.stdout)
        if "Everything is here." not in r.stdout:  # (this computer may lack some of it)
            self.assertTrue(log.exists() and log.read_text(), r.stdout + r.stderr)
        r = subprocess.run([str(ROOT / "install.sh"), "--prefix", str(self.sb.tmp / "q"), "--no-deps"], env=env,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True)
        self.assertNotIn("What vmagents uses", r.stdout)

    def test_bad_option(self):
        self.assertEqual(self.install("--nope").returncode, 2)


if __name__ == "__main__":
    unittest.main()
