#!/bin/sh
# The real vmforai, but with a made-up ntfy topic for the pictures.
if [ "$1 $2" = "phone notify" ]; then
  echo '{"on": true, "server": "https://ntfy.sh", "topic": "vmforai-7hQ2xP9aLm4Rt8Vw", "url": "https://ntfy.sh/vmforai-7hQ2xP9aLm4Rt8Vw", "app": "ntfy://ntfy.sh/vmforai-7hQ2xP9aLm4Rt8Vw", "sent": null}'
  exit 0
fi
exec /home/emin/.local/bin/vmforai "$@"
