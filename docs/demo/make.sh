#!/usr/bin/env bash
# Makes docs/demo.gif: the command line, the terminal UI and the phone page.
# Needs: a VM "arch" with ~/demo in it and Claude Code logged in (folder
# trusted), asciinema 2.4 (uv tool run --from asciinema==2.4.0 asciinema),
# agg (github.com/asciinema/agg), chromium, node, ImageMagick 7.
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

# The phone page: its server with the real VMs, then screenshots at phone size.
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

BG='#272822' W=1024 H=646
card() { magick -size ${W}x${H} xc:"$BG" -gravity center -font DejaVu-Sans-Bold -pointsize 48 -fill '#f8f8f2' \
  -annotate +0-24 "$2" -font DejaVu-Sans -pointsize 22 -fill '#a6e22e' -annotate +0+38 "$3" -delay "$4" "$1"; }
card intro.gif "vmforai" "AI coding agents in a virtual machine, not on your computer" 200
card c1.gif "1 · The command line" "give an agent a task, then take back all it did" 130
card c2.gif "2 · The terminal UI" "your VMs, and their agents in tabs: vmforai ui" 130
card c3.gif "3 · On your phone" "the same VMs in the phone's browser: terminals, tasks, notifications" 130
card outro.gif "vmforai" "github.com/emincan2000/vmforai" 300
magick cli.gif -coalesce -background "$BG" -gravity center -extent ${W}x${H} cli-pad.gif
magick ui.gif -coalesce ui-all.gif
i=0
for f in p1-list p4-task p5-log p6-runs p7-claude p2-notes; do
  magick "phone/$f.png" -resize x560 tmp.png
  w=$(magick identify -format %w tmp.png)
  magick tmp.png -alpha set \( -size "${w}x560" xc:black -fill white -draw "roundrectangle 0,0 $((w - 1)),559 22,22" \) \
    -compose CopyOpacity -composite "ph$i.png"
  i=$((i + 1))
done
slide() {
  local o=$1 a=$2 b=$3 c=$4
  shift 4
  magick -size ${W}x${H} xc:"$BG" "$1" -geometry +62+18 -composite "$2" -geometry +383+18 -composite \
    "$3" -geometry +704+18 -composite -font DejaVu-Sans -pointsize 19 -fill '#f8f8f2' -gravity NorthWest \
    -annotate +62+592 "$a" -annotate +383+592 "$b" -annotate +704+592 "$c" -delay 380 "$o"
}
slide sA.gif "Your VMs" "Give one a task" "Follow it, live" ph0.png ph1.png ph2.png
slide sB.gif "Its tasks" "Claude Code, on the phone" "Notifications (ntfy)" ph3.png ph4.png ph5.png
magick intro.gif c1.gif cli-pad.gif c2.gif ui-all.gif c3.gif sA.gif sB.gif outro.gif -loop 0 all.gif
magick all.gif -layers Optimize "$here/../demo.gif"
echo "docs/demo.gif"
