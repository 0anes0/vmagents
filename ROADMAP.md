# Roadmap

What is planned for vmagents, roughly in order. Ideas and wishes are welcome
as issues. Türkçesi: [ROADMAP.tr.md](ROADMAP.tr.md).

## Now

- [ ] Try `install.ps1` on a real Windows 10 computer (in a VM, WSL 2 hangs Windows; `tools` with Scoop works there)

## Next

- [ ] **Cost**: what each task cost (Claude Code reports it), a total per VM
      and per month, and a limit per task (`run --max-cost 2`)
- [ ] **A queue of tasks**: several tasks for one VM, done one after another
- [ ] **Issues by label**: `vmagents fix dev --label vmagents` takes on every
      open issue with that label, one by one
- [ ] **Tasks in the terminal UI**: a tab with the VM's tasks, their state and
      output (like `runs`)

## Later

- [ ] Projects and `fix` on Windows VMs
- [ ] VMs of another computer (a libvirt host over SSH) in the same list
- [ ] The AUR package published (needs an AUR account)
- [ ] A real-world tour: vmagents on a real project from start to end, and
      fixing what gets in the way

## Done lately

- [x] `vmagents deps` (Debian, Ubuntu, Fedora, Arch, openSUSE, Alpine), `install.ps1`
      for a Windows computer, `vmagents tools` for a VM (Linux, Windows through Scoop) (0.24.0)
- [x] `vmagents update`: vmagents itself, at its latest release (0.23.0)
- [x] Notifications on the phone, through ntfy: tasks and fixes ending,
      agents waiting, new VMs ready (0.23.0)
- [x] The phone page made over: a new look (light and dark), tasks given and
      followed, issues fixed, VMs started and stopped, on the home screen like
      an app, no internet needed on the same Wi-Fi (0.22.0)
- [x] `vmagents fix`: from a GitHub issue to a pull request, with the tests
      run on the VM (0.22.0)
- [x] The phone: your VMs in the phone's browser, SSH apps (0.21.0)
- [x] Tasks on Windows VMs (0.21.0)
- [x] Templates, Claude's past sessions, a load column in the UI (0.19.0, 0.20.0)
- [x] `.deb` package, AUR files (0.18.0)
- [x] Restricted network (0.17.0)
- [x] `try`: one task on several copies of the VM (0.16.0)
- [x] Yolo mode and tasks (`run`, `runs`) (0.15.0)
