import os
import pty
import select
import subprocess
import time


def run_in_pty(argv, env, cwd, send=None, answers=(), timeout=20):
    """Run argv on a pseudo-terminal. Answers prompts in order: each
    (text, reply) is sent once `text` shows up. Returns all output."""
    master, slave = pty.openpty()
    p = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave, env=env, cwd=cwd,
                         start_new_session=True)
    os.close(slave)
    answers = list(answers)
    out, pos = "", 0
    if send:
        os.write(master, send.encode())
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                try:
                    data = os.read(master, 4096)
                except OSError:  # EIO: child side closed
                    break
                if not data:
                    break
                out += data.decode(errors="replace")
            if answers and answers[0][0] in out[pos:]:
                prompt, reply = answers.pop(0)
                pos = out.index(prompt, pos) + len(prompt)
                os.write(master, reply.encode())
            if p.poll() is not None and not ready:
                break
        else:
            raise TimeoutError(f"{argv} still running; output so far:\n{out}")
        p.wait(timeout=5)
    finally:
        if p.poll() is None:
            p.kill()
        os.close(master)
    if answers:
        raise AssertionError(f"prompts never shown: {answers}\noutput:\n{out}")
    return out
