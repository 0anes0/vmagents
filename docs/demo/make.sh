#!/usr/bin/env bash
# Makes docs/demo.gif: the command line, the terminal UI and the phone page.
# Needs: a VM "arch" with ~/demo in it, Claude Code logged in (folder
# trusted) and the other four agents installed (vmforai agent arch codex, ...;
# they only start in the UI, no login needed), asciinema 2.4 (uv tool run
# --from asciinema==2.4.0 asciinema), agg (github.com/asciinema/agg), chromium,
# node, uv (for Pillow), ImageMagick 7. The phone's task changes ~/demo on
# arch: take that back before the next run.
# The phone page runs from its own server with a made-up ntfy topic
# (phone-self.sh) and a throwaway key: no real key or topic in the pictures.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
out=${1:-$here/out}
mkdir -p "$out/phone/dir" "$out/phone/cache"
cd "$out"
rec() { TERM=xterm-256color uv tool run --from 'asciinema==2.4.0' asciinema rec --overwrite -q "$@"; }
rec --cols 92 --rows 26 -c "bash $here/cli.sh" cli.cast
rec --cols 120 --rows 32 -c "python3 $here/ui.py" ui.cast
font=(--font-family "JetBrains Mono,Fira Code,DejaVu Sans Mono" --theme monokai)
agg --speed 1.5 --idle-time-limit 1.0 --last-frame-duration 2.5 --font-size 15 "${font[@]}" cli.cast cli.gif
agg --speed 1.6 --idle-time-limit 1.0 --last-frame-duration 2 --font-size 14 "${font[@]}" ui.cast ui.gif

# The phone page: its server with the real VMs, recorded at phone size.
echo demo-key >phone/dir/token
# shellcheck disable=SC2016 # Python, not the shell
python3 -c 'import sys; s=open(sys.argv[1]).read(); m="PHONE_PY=$(cat <<\x27PHONE_END\x27\n"; print(s[s.index(m)+len(m):s.index("\nPHONE_END\n")])' \
  "$(command -v vmforai)" >phone/phone.py
cp -r "${XDG_CACHE_HOME:-$HOME/.cache}/vmforai/phone-lib" phone/cache/ 2>/dev/null || true
VMFORAI_CACHE=$out/phone/cache VMFORAI_PHONE_FETCH=0 python3 phone/phone.py "$here/phone-self.sh" "$out/phone/dir" 127.0.0.1 47201 &
server=$!
trap 'kill $server 2>/dev/null' EXIT
until curl -s -o /dev/null http://127.0.0.1:47201/; do sleep 0.3; done
node "$here/phone.mjs" "$out/phone" "http://127.0.0.1:47201/#t=demo-key"
uv run -q --no-project --with pillow python "$here/phone_video.py" "$out/phone" phone.gif

BG='#272822' W=1024 H=646
card() { magick -size ${W}x${H} xc:"$BG" -gravity center -font DejaVu-Sans-Bold -pointsize 48 -fill '#f8f8f2' \
  -annotate +0-24 "$2" -font DejaVu-Sans -pointsize 22 -fill '#a6e22e' -annotate +0+38 "$3" -delay "$4" "$1"; }
card intro.gif "vmforai" "AI coding agents in a virtual machine, not on your computer" 200
card c1.gif "1 · The command line" "give an agent a task, then take back all it did" 130
card c2.gif "2 · Five agents, one terminal UI" "Claude Code, Codex, Gemini CLI, OpenCode, aider: each in a tab" 150
card c3.gif "3 · On your phone" "open a VM, give it a task, watch the agent do it" 130
card outro.gif "vmforai" "github.com/emincan2000/vmforai" 300
magick cli.gif -coalesce -background "$BG" -gravity center -extent ${W}x${H} cli-pad.gif
magick ui.gif -coalesce ui-all.gif
magick intro.gif c1.gif cli-pad.gif c2.gif ui-all.gif c3.gif phone.gif outro.gif -loop 0 all.gif
magick all.gif -layers Optimize "$here/../demo.gif"
echo "docs/demo.gif"
