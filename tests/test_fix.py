"""fix: a GitHub issue goes to an agent on the VM as a run, the tests run
there, and the work comes back as a branch with a pull request. Real git on
both sides and a local "origin"; the fake gh answers from files, the fake
agent edits and commits in the project."""
import json
import shutil

from tests.helpers import write_exe
from tests import test_projects
from tests.test_runs import TMUX

ISSUE = ("42\x1fOPEN\x1fada\x1f\x1fhttps://github.com/ada/app/issues/42\x1fThe greeting is wrong\n"
         "Issue #42: The greeting is wrong\nhttps://github.com/ada/app/issues/42\n\nIt says bad; it should say good.")

# What fix asks gh, answered from $GH_DIR; every call logged to $GH_DIR/calls.
GH = r'''#!/usr/bin/env python3
import json, os, sys
d = os.environ["GH_DIR"]
a = sys.argv[1:]
with open(os.path.join(d, "calls"), "a") as f:
    f.write(json.dumps({"argv": a, "cwd": os.getcwd()}) + "\n")
def out(name, rc=0):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        sys.exit(1)
    sys.stdout.write(open(p).read())
    sys.exit(rc)
if a[:2] == ["issue", "view"]:
    out("issue")
if a[:2] == ["api", "user"]:
    out("user")
if a[:2] == ["auth", "status"]:
    sys.exit(int(os.environ.get("GH_AUTH_RC", "0")))
if a[:2] == ["pr", "view"]:
    out("pr")
if a[:2] == ["pr", "create"]:
    print("https://github.com/ada/app/pull/7")
    sys.exit(0)
sys.exit(1)
'''

# Claude Code -p: does the work its mode says, and commits it.
AGENT = r'''#!/bin/sh
eval "task=\${$#}"
n=$(cat "$HOME/agent-count" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" >"$HOME/agent-count"
printf '%s' "$task" >"$HOME/task-$n"
case ${AGENT_MODE:-good} in
  good) echo good >fix.txt; echo "not committed" >notes.txt ;;
  bad) echo bad >fix.txt ;;
  late) if [ "$n" = 1 ]; then echo bad >fix.txt; else echo good >fix.txt; fi ;;
  loose) echo good >fix.txt; exit 0 ;;
esac
if [ "${AGENT_MODE:-good}" != nothing ]; then
  git add fix.txt && git commit -q -m "Fix the greeting" -m "Fixes #42"
fi
echo '{"type":"result","is_error":false,"num_turns":2,"duration_ms":1000,"total_cost_usd":0.05}'
exit "${AGENT_RC:-0}"
'''


class FixTests(test_projects.ProjectTests):
    # Its setUp and helpers, not its tests.
    for _name in [n for n in dir(test_projects.ProjectTests) if n.startswith("test_")]:
        locals()[_name] = None
    del _name

    def setUp(self):
        super().setUp()
        for tool in ("pwd", "sort", "kill", "python3", "readlink"):
            if shutil.which(tool) and not (self.sb.remote_bin / tool).exists():
                (self.sb.remote_bin / tool).symlink_to(shutil.which(tool))
        write_exe(self.sb.remote_bin / "tmux", TMUX)
        write_exe(self.sb.remote_bin / "claude", AGENT)
        self.gh = self.sb.tmp / "gh"
        self.gh.mkdir()
        (self.gh / "issue").write_text(ISSUE)
        (self.gh / "user").write_text("ada\n")
        write_exe(self.sb.bin / "gh", GH)
        self.sb.env.update(GH_DIR=str(self.gh), DISPLAY="")
        self.origin = self.sb.tmp / "origin.git"
        self.git("init", "-q", "--bare", str(self.origin), cwd=self.sb.tmp)
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "origin", "main")
        self.sb.run("project", "vm", str(self.repo), check=0)

    def gh_calls(self, *prefix):
        f = self.gh / "calls"
        calls = [json.loads(l)["argv"] for l in f.read_text().splitlines()] if f.exists() else []
        return [c for c in calls if c[:len(prefix)] == list(prefix)]

    def task(self, n):
        return (self.sb.remote_home / f"task-{n}").read_text()

    def test_issue_to_pull_request(self):
        test = "mkdir -p cache && touch cache/x.pyc 'report é.txt' && grep -qx good fix.txt"
        r = self.sb.run("fix", "vm", "#42", "--test", test, "--yes", check=0)
        self.assertIn("Issue #42: The greeting is wrong", r.stdout)
        self.assertIn("-- The tests pass.", r.stderr)
        self.assertNotIn("Try 2", r.stderr)
        task = self.task(1)
        self.assertIn("It says bad; it should say good.", task)
        self.assertIn(f"run the tests with `{test}`", task)
        self.assertIn('ends with "Fixes #42"', task)
        self.assertIn("only what you commit is taken", task)
        self.assertIn("do not push", task)
        self.assertFalse((self.sb.remote_home / "task-2").exists())
        # The branch here, pushed, and the pull request.
        self.assertEqual(self.git("show", "vmforai/issue-42:fix.txt"), "good")
        files = self.git("ls-tree", "-r", "--name-only", "vmforai/issue-42").splitlines()
        self.assertNotIn("cache/x.pyc", files)  # what the tests left is not part of the work
        self.assertNotIn("report é.txt", files)
        self.assertNotIn("notes.txt", files)  # nor what the agent did not commit
        self.assertIn("Left out, as the agent did not commit it: notes.txt", r.stdout)
        self.assertEqual(self.git("log", "--format=%s", "-1", "vmforai/issue-42"), "Fix the greeting")
        self.assertEqual(self.git("rev-parse", "main"), self.git("rev-parse", "HEAD"))  # checkout untouched
        self.assertEqual(self.git("rev-parse", "vmforai/issue-42", cwd=self.origin),
                         self.git("rev-parse", "vmforai/issue-42"))
        create = self.gh_calls("pr", "create")[0]
        opt = dict(zip(create[2::2], create[3::2]))
        self.assertEqual(opt["--head"], "vmforai/issue-42")
        self.assertEqual(opt["--base"], "main")
        self.assertEqual(opt["--title"], "Fix #42: The greeting is wrong")
        self.assertIn("Fixes #42.", opt["--body"])
        self.assertIn("- Fix the greeting", opt["--body"])
        self.assertIn(f"The tests (`{test}`) pass on the VM.", opt["--body"])
        self.assertIn("Made by Claude Code with `vmforai fix`", opt["--body"])
        self.assertIn("Pull request: https://github.com/ada/app/pull/7", r.stdout)
        self.assertIn(f"TEST={test}\n", self.profile())  # kept for next time

        # Next time: the test command from the profile, and a fresh copy although
        # the last work was taken back but not merged.
        (self.gh / "pr").write_text("https://github.com/ada/app/pull/7\n")
        r = self.sb.run("fix", "vm", "42", check=0)
        self.assertIn("-- The tests pass.", r.stderr)
        self.assertIn("its pull request was open already: https://github.com/ada/app/pull/7", r.stdout)
        self.assertEqual(len(self.gh_calls("pr", "create")), 1)

    def test_failing_tests_go_back_to_the_agent(self):
        r = self.sb.run("fix", "vm", "42", "--test", "grep -x good fix.txt || { echo 'expected good'; exit 1; }",
                        env={"AGENT_MODE": "late"}, check=0)
        self.assertIn("-- Try 1 of 2", r.stderr)
        self.assertIn("-- The tests fail.", r.stderr)
        self.assertIn("-- Try 2 of 2", r.stderr)
        self.assertIn("expected good", r.stdout)
        task = self.task(2)
        self.assertIn("It says bad; it should say good.", task)
        self.assertIn("But the tests fail:", task)
        self.assertIn("expected good", task)
        self.assertEqual(self.git("show", "vmforai/issue-42:fix.txt"), "good")
        self.assertEqual(len(self.gh_calls("pr", "create")), 1)

    def test_still_failing_no_pull_request(self):
        r = self.sb.run("fix", "vm", "42", "--test", "grep -qx good fix.txt", "--tries", "1",
                        env={"AGENT_MODE": "bad"})
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("still fail after 1 tries, so no pull request", r.stdout)
        self.assertEqual(self.git("show", "vmforai/issue-42:fix.txt"), "bad")  # there to look at
        self.assertEqual(self.gh_calls("pr", "create"), [])
        self.assertNotIn("vmforai/issue-42", self.git("branch", "--list", "-r"))

    def test_agent_that_does_not_commit(self):
        r = self.sb.run("fix", "vm", "42", "--no-pr", env={"AGENT_MODE": "loose"}, check=0)
        self.assertEqual(self.git("show", "vmforai/issue-42:fix.txt"), "good")  # then all it left is taken
        self.assertNotIn("Left out", r.stdout)

    def test_nothing_changed(self):
        r = self.sb.run("fix", "vm", "42", "--no-pr", env={"AGENT_MODE": "nothing"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("the agent changed nothing", r.stderr)
        self.assertEqual(self.git("branch", "--list", "vmforai/issue-42"), "")

    def test_agent_failure_stops_it(self):
        r = self.sb.run("fix", "vm", "42", env={"AGENT_RC": "3"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("did not finish well", r.stderr)
        self.assertEqual(self.git("branch", "--list", "vmforai/issue-42"), "")

    def test_without_tests_and_pull_request(self):
        r = self.sb.run("fix", "vm", "42", "--no-pr", "--branch", "fix/greeting", check=0)
        self.assertIn("run the tests of the project, if it has any", self.task(1))
        self.assertEqual(self.git("show", "fix/greeting:fix.txt"), "good")
        self.assertIn("take vm --branch fix/greeting --pr", r.stdout)
        self.assertEqual(self.gh_calls("pr"), [])
        self.assertEqual(self.gh_calls("auth"), [])

    def test_draft_without_test_command(self):
        self.sb.run("fix", "vm", "42", "--draft", check=0)
        create = self.gh_calls("pr", "create")[0]
        self.assertIn("--draft", create)
        self.assertIn("Not tested by vmforai", create[create.index("--body") + 1])

    def test_text_by_others_asks_first(self):
        (self.gh / "issue").write_text(ISSUE.replace("\x1fada\x1f\x1f", "\x1fmallory\x1fada bob\x1f", 1))
        r = self.sb.run("fix", "vm", "42")
        self.assertEqual(r.returncode, 1)
        self.assertIn("has text by mallory bob, not you", r.stderr)
        self.assertIn("without --yes", r.stderr)
        self.assertFalse((self.sb.remote_home / "task-1").exists())
        r = self.sb.run("fix", "vm", "42", "--no-pr", input="y\n")  # not a terminal: still no
        self.assertEqual(r.returncode, 1)
        self.sb.run("fix", "vm", "42", "--no-pr", "--yes", check=0)
        self.assertTrue((self.sb.remote_home / "task-1").exists())

    def test_work_not_taken_back(self):
        (self.vm_repo / "mine.txt").write_text("by hand\n")
        r = self.sb.run("fix", "vm", "42", "--no-pr")
        self.assertEqual(r.returncode, 5)
        self.assertIn("vmforai fix vm 42 --discard", r.stderr)
        self.sb.run("fix", "vm", "42", "--no-pr", "--discard", check=0)
        self.assertNotIn("mine.txt", self.git("ls-tree", "--name-only", "vmforai/issue-42"))

    def test_problems(self):
        self.assertIn("which issue?", self.sb.run("fix", "vm").stderr)
        self.assertIn("--tries takes 1 to 9", self.sb.run("fix", "vm", "1", "--tries", "0").stderr)
        (self.gh / "issue").unlink()
        self.assertIn("could not read issue 9", self.sb.run("fix", "vm", "9").stderr)
        (self.gh / "issue").write_text(ISSUE)
        r = self.sb.run("fix", "vm", "42", env={"GH_AUTH_RC": "1"})
        self.assertIn("gh is not logged in", r.stderr)
        self.assertFalse((self.sb.remote_home / "task-1").exists())  # checked before the agent's work
        self.git("remote", "remove", "origin")
        self.assertIn("no remote origin", self.sb.run("fix", "vm", "42").stderr)
        self.sb.run("project", "vm", "--off", check=0)
        self.assertIn("vm has no project", self.sb.run("fix", "vm", "42").stderr)

    def test_the_test_command_goes_with_the_project(self):
        self.sb.run("fix", "vm", "42", "--no-pr", "--test", "true", check=0)
        self.assertIn("TEST=true\n", self.profile())
        self.sb.run("project", "vm", "--off", check=0)
        self.assertNotIn("TEST=", self.profile())

    def test_vm_that_was_off_goes_off_again(self):
        self.sb.set_vm("shut off")
        self.sb.run("fix", "vm", "42", "--no-pr", check=0)
        self.assertIn("start", self.virsh_cmds())
        self.assertEqual(self.state(), "shut off")

    def test_help(self):
        self.assertIn("vmforai fix NAME ISSUE", self.sb.run("help", "fix", check=0).stdout)
        self.assertIn("fix NAME ISSUE", self.sb.run("help", check=0).stdout)
