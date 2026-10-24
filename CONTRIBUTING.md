# Contributing

Thank you for wanting to help. Issues and pull requests in English or
Turkish are both welcome.

## How it is built

- `vmagents` is one Bash script. The terminal UI (Python, Textual), the phone
  page's server and a few other helpers live inside it as heredocs
  (`UI_PY`, `PHONE_PY`, ...), so that installing is copying one file.
- Scripts that run on the VM are kept in variables (`..._SH` for Linux, `..._PS`
  for Windows) and sent over SSH.
- The README (English and Turkish) is the documentation; `vmagents help
  COMMAND` has the details of each command.

## Tests

```sh
python3 -m unittest discover -s tests -t .
# with the UI tests (they need Textual and pyte):
uv run --no-project --with 'textual>=8,<9' --with pyte --with qrcode python -m unittest discover -s tests -t .
shellcheck vmagents install.sh packaging/deb/build.sh packaging/aur/update.sh
```

The tests run vmagents against fake `ssh`, `virsh`, `virt-install`, `curl`
and package managers; the scripts meant for the VM really run, under `sh`, in
a temporary home folder. They never touch your VMs or your settings. CI runs
the same on every push.

A change that touches a real VM is worth trying on one too (a VM made with
`vmagents create`, which `vmagents delete` removes afterwards); say in the
pull request what you tried.

## Style

- Plain words in messages and docs: what happens, what to do next.
- Comments say why, not what; match the code around.
- No new dependencies on your computer or the VM without a good reason.
