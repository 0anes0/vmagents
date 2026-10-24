"""Drives vmforai ui on a pty of its own (120x32) and copies what it draws to
stdout, for asciinema (docs/demo/make.sh). Keys at set moments: Claude Code in a
tab answers a question, then F3 to F6 open the other four agents as tabs
and three of them answer it too."""
import fcntl, os, pty, select, struct, sys, termios, time

COLS, ROWS = 120, 32
pid, fd = pty.fork()
if pid == 0:
    os.environ.update(TERM="xterm-256color", COLORTERM="truecolor")
    os.execvp("vmforai", ["vmforai", "ui"])
fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
seen = b""

def pump(seconds):
    global seen
    end = time.time() + seconds
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            try:
                data = os.read(fd, 65536)
            except OSError:
                return
            seen = (seen + data)[-200000:]
            sys.stdout.buffer.write(data)
            sys.stdout.flush()

def wait_for(text, seconds=30):
    global seen
    end = time.time() + seconds
    while time.time() < end and text.encode() not in seen:
        pump(0.2)

def key(k, pause=0.8):
    os.write(fd, k.encode())
    pump(pause)

def typed(text, pause=0.6):
    for ch in text:
        os.write(fd, ch.encode())
        pump(0.05)
    pump(pause)

wait_for("Enter or l", 30)
pump(3.5)
key("j", 2)              # arch: its details on the right
key("\r", 1.8)           # open as...
seen = b""
key("j", 0.8)
key("\r", 1)             # Claude Code, in a tab
wait_for("to cycle", 30)
pump(1.5)
ASK = "A Python one-liner for the sum of the squares of 1 to 10. Just the code, no tools."


def ask(text, until):
    """Types a question into the agent in the open tab and waits for its answer."""
    global seen
    typed(text, 0.5)
    key("\r", 1)
    seen = b""
    wait_for(until, 120)
    pump(7)              # the rest of the answer (it may stream, or think first)


if b"to cycle" in seen:
    ask(ASK, "print")    # not in the question; colours split "print("
# F3 to F6: Codex, Gemini CLI, OpenCode, aider. Codex, OpenCode and aider answer too
# (through OpenRouter's free models, see make.sh); Gemini CLI only starts.
for f, text in (("\x1bOR", ASK), ("\x1bOS", None), ("\x1b[15~", ASK), ("\x1b[17~", "/ask " + ASK)):
    key(f, 4)
    if text:
        ask(text, "range")
key("\x1d", 3)          # Ctrl+]: back to the list, the five tabs above it
key("q", 2.5)          # "5 terminals are open...": the recording ends on it
os.kill(pid, 9)
