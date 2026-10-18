"""Projects: a git repository of this computer sent to the VM (project), the
agents' work looked at (changes) and brought back as a branch (take). With
real git on both sides; the fake ssh runs the VM's side locally."""
import json
import os
import shutil
import subprocess

from tests.test_create import CreateBase
from tests.test_stop import Base

GIT_ENV = {"GIT_AUTHOR_NAME": "Ada", "GIT_AUTHOR_EMAIL": "ada@example.com", "GIT_COMMITTER_NAME": "Ada",
           "GIT_COMMITTER_EMAIL": "ada@example.com", "GIT_CONFIG_NOSYSTEM": "1"}


class ProjectTests(Base):
    def setUp(self):
        super().setUp()
        for tool in ("git", "mktemp"):
            (self.sb.remote_bin / tool).symlink_to(shutil.which(tool))
        self.sb.env.update(STUB_SSH_EXEC="1", GIT_CONFIG_NOSYSTEM="1")
        self.repo = self.sb.tmp / "code" / "app"
        self.repo.mkdir(parents=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Ada")
        self.git("config", "user.email", "ada@example.com")
        (self.repo / "a.txt").write_text("one\n")
        (self.repo / ".gitignore").write_text("node_modules/\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "first")
        self.vm_repo = self.sb.remote_home / "projects" / "app"

    def git(self, *args, cwd=None):
        env = dict(os.environ, HOME=str(self.sb.home), **GIT_ENV)
        return subprocess.run(["git", *args], cwd=cwd or self.repo, env=env, check=True, capture_output=True,
                              text=True).stdout.strip()

    def vm_git(self, *args):
        return self.git(*args, cwd=self.vm_repo)

    def agent_works(self):
        """What an agent does on the VM: a commit, a change and a new file left uncommitted."""
        (self.vm_repo / "c.txt").write_text("committed\n")
        self.vm_git("add", "c.txt")
        self.vm_git("commit", "-q", "-m", "add c")
        (self.vm_repo / "a.txt").write_text("one\nchanged on the VM\n")
        (self.vm_repo / "b.txt").write_text("new\n")
        (self.vm_repo / "node_modules").mkdir()
        (self.vm_repo / "node_modules" / "x.js").write_text("ignored\n")

    def test_round_trip(self):
        r = self.sb.run("project", "vm", str(self.repo), check=0)
        self.assertIn("Sent main (", r.stdout)
        self.assertIn("~/projects/app", r.stdout)
        self.assertEqual((self.vm_repo / "a.txt").read_text(), "one\n")
        self.assertEqual(self.vm_git("symbolic-ref", "--short", "HEAD"), "main")
        self.assertEqual(self.vm_git("config", "user.name"), "Ada")  # commits there are the user's
        profile = self.profile()
        self.assertIn(f"PROJECT={self.repo}\n", profile)
        self.assertIn("DIR=~/projects/app\n", profile)
        self.assertEqual(json.loads(self.sb.run("list", "--json", check=0).stdout)[0]["project"], str(self.repo))
        self.assertIn("No changes on vm", self.sb.run("changes", "vm", check=0).stdout)

        self.agent_works()
        out = self.sb.run("changes", "vm", check=0).stdout
        self.assertIn("add c", out)
        self.assertIn("Work not committed on the VM", out)
        self.assertIn("+changed on the VM", out)
        self.assertIn("b.txt", out)
        self.assertNotIn("node_modules", out)  # ignored files stay
        self.assertNotIn("+changed", self.sb.run("changes", "vm", "--stat", check=0).stdout)
        self.assertEqual(self.git("branch", "--list", "vmagents/vm"), "")  # changes makes no branch
        self.assertIn("M a.txt", self.vm_git("status", "--short"))  # nor touches the VM

        # Sending again would overwrite that work: refused.
        r = self.sb.run("project", "vm")
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertIn("was not taken back", r.stderr)
        self.assertEqual((self.vm_repo / "b.txt").read_text(), "new\n")

        head = self.git("rev-parse", "HEAD")
        r = self.sb.run("take", "vm", check=0)
        self.assertIn("the branch vmagents/vm", r.stdout)
        self.assertIn("git merge vmagents/vm", r.stdout)
        self.assertEqual(self.git("show", "vmagents/vm:b.txt"), "new")
        self.assertEqual(self.git("show", "vmagents/vm:c.txt"), "committed")
        self.assertEqual(self.git("log", "--format=%s", "-2", "vmagents/vm").splitlines(),
                         ["Work not committed on the VM", "add c"])
        self.assertEqual(self.git("rev-parse", "HEAD"), head)  # the checkout here is not touched
        self.assertFalse((self.repo / "b.txt").exists())

        # Merged here, with one more commit: it goes back, and the VM goes on from there.
        self.git("merge", "-q", "--ff-only", "vmagents/vm")
        (self.repo / "d.txt").write_text("from here\n")
        self.git("add", "d.txt")
        self.git("commit", "-q", "-m", "add d")
        self.sb.run("project", "vm", check=0)
        self.assertEqual(self.vm_git("rev-parse", "HEAD"), self.git("rev-parse", "HEAD"))
        self.assertEqual(self.vm_git("status", "--short", "--untracked-files=all"), "")
        self.assertEqual((self.vm_repo / "d.txt").read_text(), "from here\n")
        self.assertTrue((self.vm_repo / "node_modules" / "x.js").exists())  # ignored files are kept
        self.assertIn("No changes", self.sb.run("changes", "vm", check=0).stdout)

    def test_taken_but_not_merged_is_refused(self):
        self.sb.run("project", "vm", str(self.repo), check=0)
        self.agent_works()
        self.sb.run("take", "vm", check=0)
        self.assertEqual(self.sb.run("project", "vm").returncode, 5)  # not in what would be sent

    def test_discard(self):
        self.sb.run("project", "vm", str(self.repo), check=0)
        self.agent_works()
        self.sb.run("project", "vm", "--discard", check=0)
        self.assertEqual(self.vm_git("status", "--short"), "")
        self.assertFalse((self.vm_repo / "b.txt").exists())
        kept = self.vm_git("for-each-ref", "--format=%(refname)", "refs/vmagents/discarded/")
        self.assertTrue(kept.startswith("refs/vmagents/discarded/"))
        self.assertEqual(self.vm_git("show", f"{kept}:b.txt"), "new")  # set aside, not lost

    def test_take_to_a_branch_of_your_choice(self):
        self.sb.run("project", "vm", str(self.repo), check=0)
        self.agent_works()
        self.assertIn("is checked out", self.sb.run("take", "vm", "--branch", "main").stderr)
        self.assertIn("not a valid branch", self.sb.run("take", "vm", "--branch", "a..b").stderr)
        self.sb.run("take", "vm", "--branch", "feature/x", check=0)
        self.assertEqual(self.git("show", "feature/x:b.txt"), "new")

    def test_nothing_to_take(self):
        self.sb.run("project", "vm", str(self.repo), check=0)
        self.assertIn("Nothing to take", self.sb.run("take", "vm", check=0).stdout)
        self.assertEqual(self.git("branch", "--list", "vmagents/vm"), "")

    def test_new_commits_only(self):
        self.sb.run("project", "vm", str(self.repo), check=0)
        for i in range(3):
            (self.repo / f"f{i}.txt").write_text(f"{i}\n")
            self.git("add", ".")
            self.git("commit", "-q", "-m", f"commit {i}")
        self.sb.clear_log()
        self.sb.run("project", "vm", check=0)  # the profile remembers the folder
        header = self.sb.calls("ssh")[-1]["stdin"].split("\n")
        self.assertEqual(header[0], "# v2 git bundle")
        self.assertTrue(header[1].startswith("-"), header[:3])  # needs what the VM has: only new commits went
        self.assertEqual(self.vm_git("log", "--format=%s", "-1"), "commit 2")
        self.sb.clear_log()
        self.assertIn("Sent main", self.sb.run("project", "vm", check=0).stdout)  # nothing new: still fine
        self.assertEqual(self.sb.calls("ssh")[-1]["stdin"], "")

    def test_problems(self):
        plain = self.sb.tmp / "plain"
        plain.mkdir()
        self.assertIn("is not in a git repository", self.sb.run("project", "vm", str(plain)).stderr)
        self.assertIn("vm has no project", self.sb.run("changes", "vm").stderr)
        self.assertIn("vm has no project", self.sb.run("take", "vm").stderr)
        (self.sb.remote_home / "projects" / "app").mkdir(parents=True)
        (self.sb.remote_home / "projects" / "app" / "mine.txt").write_text("keep me\n")
        r = self.sb.run("project", "vm", str(self.repo))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("has files and is not a git repository", r.stderr)
        self.assertEqual((self.sb.remote_home / "projects" / "app" / "mine.txt").read_text(), "keep me\n")
        self.assertNotIn("PROJECT=", self.profile())

    def test_off(self):
        self.sb.run("project", "vm", str(self.repo), check=0)
        self.assertIn("has no project any more", self.sb.run("project", "vm", "--off", check=0).stdout)
        self.assertNotIn("PROJECT=", self.profile())
        self.assertNotIn("DIR=", self.profile())

    def test_vm_that_was_off_goes_off_again(self):
        self.sb.set_vm("shut off")
        self.sb.run("project", "vm", str(self.repo), check=0)
        self.assertIn("start", self.virsh_cmds())
        self.assertEqual(self.state(), "shut off")

    def test_help(self):
        for cmd in ("project", "changes", "take"):
            self.assertIn(f"vmagents {cmd} NAME", self.sb.run("help", cmd, check=0).stdout)


class CreateWithProjectTests(CreateBase):
    def test_create_checks_the_project_first(self):
        r = self.sb.run("create", "box", "--project", str(self.sb.tmp), "--no-setup")
        self.assertIn("--project:", r.stderr)
        self.assertNotIn("virt-install", [c["prog"] for c in self.sb.calls()])
