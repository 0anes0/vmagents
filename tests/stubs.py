"""Fake ssh / virsh / tools used by the tests. Each stub logs its argv."""

SSH = r'''#!/usr/bin/env python3
# Fake ssh: logs argv; with STUB_SSH_EXEC=1 runs the remote command locally
# under sh, with HOME=$STUB_REMOTE_HOME, like sshd would.
import json, os, subprocess, sys
args = sys.argv[1:]
stdin = b"" if sys.stdin is None or sys.stdin.isatty() else sys.stdin.buffer.read()
with open(os.environ["STUB_LOG"], "a") as f:
    f.write(json.dumps({"prog": "ssh", "argv": args, "stdin": stdin.decode(errors="replace")}) + "\n")
# Key-login probes (`ssh ... true`) pop their exit code from a list.
if args[-1] == "true" and os.environ.get("STUB_SSH_BATCH_RC"):
    rc_file = os.environ["STUB_SSH_BATCH_RC"]
    codes = open(rc_file).read().split()
    open(rc_file, "w").write(" ".join(codes[1:] or codes))
    sys.exit(int(codes[0]))
if os.environ.get("STUB_SSH_EXEC") == "1":
    i = args.index("--")
    cmd = " ".join(args[i + 2:])
    env = dict(os.environ, HOME=os.environ["STUB_REMOTE_HOME"])
    env["PATH"] = os.environ.get("STUB_REMOTE_PATH", env["PATH"])
    r = subprocess.run(["sh", "-c", cmd], input=stdin, env=env, cwd=env["HOME"])
    sys.exit(r.returncode)
sys.exit(int(os.environ.get("STUB_SSH_RC", "0")))
'''

VIRSH = r'''#!/usr/bin/env python3
# Fake virsh. State in $STUB_VIRSH_STATE: "<state> <ip> <ip_after_polls>".
import json, os, sys
args = sys.argv[1:]
with open(os.environ["STUB_LOG"], "a") as f:
    f.write(json.dumps({"prog": "virsh", "argv": args}) + "\n")
path = os.environ["STUB_VIRSH_STATE"]
state, ip, polls = open(path).read().split("|")
polls = int(polls)
if "-c" in args:
    i = args.index("-c"); args = args[:i] + args[i + 2:]
cmd = args[0]
if args[1:2] and args[1] != os.environ.get("STUB_VIRSH_DOMAIN", "testvm") and cmd != "list":
    print(f"error: failed to get domain '{args[1]}'", file=sys.stderr); sys.exit(1)
if cmd == "domstate":
    print(state); print(); sys.exit(0)
if cmd == "start":
    if state == "running":
        print("error: Domain is already active", file=sys.stderr); sys.exit(1)
    open(path, "w").write(f"running|{ip}|{polls}"); print("Domain started"); sys.exit(0)
if cmd == "resume":
    open(path, "w").write(f"running|{ip}|{polls}"); sys.exit(0)
if cmd == "domifaddr":
    src = args[args.index("--source") + 1] if "--source" in args else "lease"
    print(" Name       MAC address          Protocol     Address")
    print("-------------------------------------------------------------------------------")
    if src == "agent":
        print(" lo         00:00:00:00:00:00    ipv4         127.0.0.1/8")
    if state == "running" and src == "lease":
        if polls > 0:
            open(path, "w").write(f"{state}|{ip}|{polls - 1}")
        elif ip:
            print(f" vnet0      52:54:00:12:34:56    ipv4         {ip}/24")
    print(); sys.exit(0)
if cmd == "list":
    print("testvm"); print(); sys.exit(0)
print("unsupported", args, file=sys.stderr); sys.exit(1)
'''

# Records argv on the "remote" side and prints it, for claude/tmux/sudo/...
RECORDER = r'''#!/bin/sh
{ printf '%s' "$(basename "$0")"; for a in "$@"; do printf ' [%s]' "$a"; done; printf ' cwd=[%s]\n' "$PWD"; } >>"$STUB_REMOTE_LOG"
case $(basename "$0") in
  claude) [ "${1-}" = --version ] && echo "9.9.9 (Claude Code)" ;;
  tmux) [ "${1-}" = -V ] && echo "tmux 3.5" ;;
esac
exit 0
'''

# Fake `curl -fsSL https://claude.ai/install.sh`: emits an installer script.
CURL = r'''#!/bin/sh
printf '%s ' "curl" "$@" >>"$STUB_REMOTE_LOG"; echo >>"$STUB_REMOTE_LOG"
cat <<'EOS'
mkdir -p "$HOME/.local/bin"
cp "$STUB_RECORDER" "$HOME/.local/bin/claude"
chmod +x "$HOME/.local/bin/claude"
echo "installer ran"
EOS
'''
