"""history: Claude Code's sessions on the VM (~/.claude/projects/DIR/ID.jsonl),
listed and shown readable, with the VM's scripts run under sh and python3
in the fake VM's home."""
import json
import os
import shutil
import time

from tests.test_stop import Base


def line(**e):
    return json.dumps(e) + "\n"


class HistoryTests(Base):
    def setUp(self):
        super().setUp()
        if not (self.sb.remote_bin / "python3").exists():
            (self.sb.remote_bin / "python3").symlink_to(shutil.which("python3"))
        self.sb.env["STUB_SSH_EXEC"] = "1"
        d = self.sb.remote_home / ".claude" / "projects" / "-home-me-app"
        d.mkdir(parents=True)
        old = d / "aaaa-old.jsonl"
        old.write_text(
            line(type="queue-operation")
            + line(type="user", cwd="/home/me/app", timestamp="2026-10-17T10:00:00Z",
                   message={"role": "user", "content": "<command-name>/clear</command-name>"})
            + line(type="user", cwd="/home/me/app", message={"role": "user", "content": "add a /health endpoint"})
            + line(type="assistant", message={"content": [
                {"type": "text", "text": "I will add it to server.ts."},
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "/home/me/app/server.ts"}}]})
            + line(type="user", message={"content": [{"type": "tool_result", "content": "ok"}]})
            + line(type="assistant", message={"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "npm test"}},
                {"type": "text", "text": "Done: GET /health answers ok."}]})
            + "not json\n")
        os.utime(old, (time.time() - 3600, time.time() - 3600))
        (d / "bbbb-new.jsonl").write_text(
            line(type="user", cwd="/home/me/app", message={"role": "user", "content": "fix the\nfailing tests"})
            + line(type="assistant", message={"content": [{"type": "text", "text": "Fixed."}]}))
        (d / "cccc-empty.jsonl").write_text(line(type="queue-operation"))  # nothing said: not listed

    def test_list_and_show(self):
        out = self.sb.run("history", "vm", check=0).stdout
        rows = [l for l in out.splitlines() if l[:1].isdigit()]
        self.assertEqual(len(rows), 2)
        self.assertRegex(rows[0], r"^1 +\d{4}-\d\d-\d\d \d\d:\d\d +2 +/home/me/app +fix the failing tests$")
        self.assertRegex(rows[1], r"^2 .* 3 +/home/me/app +add a /health endpoint$")
        data = json.loads(self.sb.run("history", "vm", "--json", check=0).stdout)
        self.assertEqual([s["id"] for s in data], ["bbbb-new", "aaaa-old"])
        self.assertEqual(data[1]["start"], "2026-10-17T10:00:00Z")
        shown = self.sb.run("history", "vm", "2", check=0).stdout
        self.assertIn("> add a /health endpoint\n", shown)
        self.assertIn("I will add it to server.ts.\n", shown)
        self.assertIn("* Edit(/home/me/app/server.ts)\n", shown)
        self.assertIn("* Bash(npm test)\n", shown)
        self.assertIn("Done: GET /health answers ok.", shown)
        self.assertNotIn("/clear", shown)
        self.assertIn("Go on with it: vmforai vm --resume aaaa-old", shown)
        self.assertIn("> fix the\n  failing tests", self.sb.run("history", "vm", "bbbb-new", check=0).stdout)
        self.assertIn("no session 7 on vm", self.sb.run("history", "vm", "7").stderr)
        self.assertIn("no session nope on vm", self.sb.run("history", "vm", "nope").stderr)
        self.assertIn("vmforai history NAME", self.sb.run("help", "history", check=0).stdout)

    def test_none_yet(self):
        shutil.rmtree(self.sb.remote_home / ".claude")
        self.assertIn("No Claude Code sessions on vm yet.", self.sb.run("history", "vm", check=0).stdout)
        self.assertEqual(json.loads(self.sb.run("history", "vm", "--json", check=0).stdout), [])
