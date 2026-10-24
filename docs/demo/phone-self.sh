#!/bin/sh
# The real vmagents, but with a made-up ntfy topic for the pictures.
if [ "$1 $2" = "phone notify" ]; then
  echo '{"on": true, "server": "https://ntfy.sh", "topic": "vmagents-7hQ2xP9aLm4Rt8Vw", "url": "https://ntfy.sh/vmagents-7hQ2xP9aLm4Rt8Vw", "app": "ntfy://ntfy.sh/vmagents-7hQ2xP9aLm4Rt8Vw", "sent": null}'
  exit 0
fi
exec /home/emin/.local/bin/vmagents "$@"
