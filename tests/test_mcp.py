"""vmclaude mcp NAME: the MCP server, spoken to like Claude Code does, with the
fake ssh/scp running everything in a throwaway "VM" home on this machine."""
import json
import subprocess

from tests.helpers import write_exe

from tests.helpers import VMCLAUDE, SandboxTest


class McpTests(SandboxTest):
    def setUp(self):
        super().setUp()
        self.sb.run("add", "vm", "--host", "192.0.2.7", "--os", "linux", "--dir", "~/work", check=0)
        self.p = subprocess.Popen([str(VMCLAUDE), "mcp", "vm"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, cwd=self.sb.tmp,
                                  env=dict(self.sb.env, STUB_SSH_EXEC="1"))
        self.addCleanup(self.close)
        self.n = 0

    def close(self):
        if self.p.poll() is None:
            self.p.stdin.close()
            self.p.wait(10)
        self.p.stdout.close()
        self.p.stderr.close()

    def rpc(self, method, params=None):
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}}) + "\n")
        self.p.stdin.flush()
        msg = json.loads(self.p.stdout.readline())
        self.assertEqual(msg["id"], self.n)
        return msg

    def call(self, tool, **args):
        r = self.rpc("tools/call", {"name": tool, "arguments": args})["result"]
        return r["content"][0]["text"], r["isError"]

    def test_handshake_and_tools(self):
        r = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})["result"]
        self.assertEqual(r["protocolVersion"], "2025-06-18")
        self.assertEqual(r["serverInfo"]["name"], "vmclaude-vm")
        self.assertIn("virtual machine 'vm'", r["instructions"])
        self.p.stdin.write('{"jsonrpc": "2.0", "method": "notifications/initialized"}\n')
        tools = {t["name"]: t for t in self.rpc("tools/list")["result"]["tools"]}
        self.assertEqual(sorted(tools), ["edit_file", "read_file", "run", "write_file"])
        self.assertEqual(tools["run"]["inputSchema"]["required"], ["command"])
        self.assertIn("Linux", tools["run"]["description"])
        self.assertEqual(self.rpc("ping")["result"], {})
        self.assertEqual(self.rpc("nope")["error"]["code"], -32601)
        self.assertEqual(self.rpc("tools/call", {"name": "nope"})["error"]["code"], -32602)

    def test_run(self):
        out, err = self.call("run", command="pwd; echo oops >&2; exit 3")
        work = self.sb.remote_home / "work"
        self.assertFalse(err)
        self.assertEqual(out, f"{work}\n[stderr]\noops\n[exit code 3]")
        self.assertTrue(work.is_dir())  # created on first use
        out, err = self.call("run", command="printf '%s' \"it's $((6*7))\"")
        self.assertEqual(out, "it's 42\n[exit code 0]")
        self.assertTrue(self.call("run", command="  ")[1])

    def test_files(self):
        out, err = self.call("write_file", path="src/a.py", content="x = 1\ny = 'ğüş'\n")
        f = self.sb.remote_home / "work" / "src" / "a.py"
        self.assertEqual(out, f"Wrote 19 bytes to {f}")
        self.assertEqual(f.read_text(), "x = 1\ny = 'ğüş'\n")
        out, _ = self.call("read_file", path="~/work/src/a.py")
        self.assertEqual(out, f"{f} (2 lines)\n     1\tx = 1\n     2\ty = 'ğüş'")
        out, _ = self.call("read_file", path=str(f), offset=2, limit=1)
        self.assertTrue(out.endswith("     2\ty = 'ğüş'"))
        self.assertEqual(self.call("edit_file", path="src/a.py", old_string="x = 1", new_string="x = 2")[0],
                         f"Edited {f}: replaced 1 occurrence(s)")
        self.assertEqual(f.read_text(), "x = 2\ny = 'ğüş'\n")

    def test_edit_rules(self):
        f = self.sb.remote_home / "work" / "t.txt"
        f.parent.mkdir()
        f.write_bytes(b"a\r\nb\r\na\r\n")
        out, err = self.call("edit_file", path="t.txt", old_string="a", new_string="c")
        self.assertTrue(err)
        self.assertIn("occurs 2 times", out)
        self.assertFalse(self.call("edit_file", path="t.txt", old_string="a", new_string="c", replace_all=True)[1])
        self.assertEqual(f.read_bytes(), b"c\r\nb\r\nc\r\n")
        # an old_string with \n still matches a file with \r\n line ends
        self.assertFalse(self.call("edit_file", path="t.txt", old_string="b\nc", new_string="B\nC")[1])
        self.assertEqual(f.read_bytes(), b"c\r\nB\r\nC\r\n")
        out, err = self.call("edit_file", path="t.txt", old_string="zzz", new_string="")
        self.assertTrue(err)
        self.assertIn("not found", out)

    def test_errors_keep_the_server_running(self):
        out, err = self.call("read_file", path="/nonexistent/file")
        self.assertTrue(err)
        self.assertIn("cannot read /nonexistent/file", out)
        out, err = self.call("run", command="sleep 5", timeout=1)
        self.assertTrue(err)
        self.assertEqual(out, "timed out after 1 s")
        self.assertEqual(self.call("run", command="echo still here")[0], "still here\n[exit code 0]")

    def test_unreachable_vm(self):
        self.sb.env["STUB_SSH_RC"] = "255"
        p = subprocess.run([str(VMCLAUDE), "mcp", "vm"], input='{"jsonrpc":"2.0","id":1,"method":"tools/call",'
                           '"params":{"name":"run","arguments":{"command":"true"}}}\n', capture_output=True, text=True,
                           env=dict(self.sb.env, STUB_SSH_RC="255"), timeout=30)
        r = json.loads(p.stdout)["result"]
        self.assertTrue(r["isError"])
        self.assertIn("cannot reach VM vm", r["content"][0]["text"])
        self.assertIn("vmclaude doctor vm", r["content"][0]["text"])


class McpAddTests(SandboxTest):
    def test_add_registers_with_claude(self):
        self.sb.run("add", "vm", "--host", "192.0.2.7", "--os", "linux", check=0)
        log = self.sb.tmp / "claude.args"
        write_exe(self.sb.bin / "claude", f'#!/bin/sh\nprintf "%s\\n" "$@" > {log}\n')
        r = self.sb.run("mcp", "vm", "--add", check=0)
        self.assertIn("claude mcp remove vm --scope user", r.stdout)
        self.assertEqual(log.read_text().splitlines(),
                         ["mcp", "add", "--scope", "user", "vm", "--", str(VMCLAUDE.resolve()), "mcp", "vm"])
        self.assertEqual(self.sb.run("mcp", "nope", "--add").returncode, 1)
