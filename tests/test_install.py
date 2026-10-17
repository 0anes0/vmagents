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
        self.assertIn("is not on your PATH", r.stdout)
        r = self.install("--prefix", str(prefix), "--uninstall")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(binary.exists())

    def test_bad_option(self):
        self.assertEqual(self.install("--nope").returncode, 2)


if __name__ == "__main__":
    unittest.main()
