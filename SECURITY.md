# Security

vmforai runs agents that act without asking, gives phones a way into your
VMs, and keeps tokens in a few files. If you find a way around any of that
(the phone page's key, the restricted network, the files' permissions, or
anything else), please report it privately:
[Report a vulnerability](https://github.com/emincan2000/vmforai/security/advisories/new).

You will get an answer within a few days, and credit in the release notes if
you want it.

What vmforai does and does not promise:

- A VM keeps the agent away from your computer's files and keys, as far as the
  hypervisor does. It is not a defence against a determined attacker who
  breaks out of QEMU/KVM.
- The agent has the VM's network unless you restrict it (`vmforai net NAME
  restricted`), and the credentials you gave it there (Claude's login, an API
  key) can be read by what runs in the VM.
- The phone page is as safe as its link: the key in it gives access to your
  VMs' terminals. It listens on Tailscale (encrypted) or, with `--lan`, on your
  local network without encryption.
