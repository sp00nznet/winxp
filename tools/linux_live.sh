#!/bin/sh
# A live run under Xvfb, driven like a person at the keyboard and mouse:
#   sh linux_live.sh APP OUT [xdotool steps ...]
# e.g. (in the scratch directory's root/, after linux_build.sh ntsol):
#   sh ../linux_live.sh sol out/live "mousemove 60 100" "click 1" "sleep 1" "shot deck"
#   sh ../linux_live.sh notepad out/np "type 'Hello, Windows 2000'" "key Return" "shot typed"
# Each step is an xdotool command line run against the app's X window, or
# "shot NAME" (an xwd of the window, as OUT_NAME.png). The app runs with
# --live (w32kposix's X11 frontend, real input). With a DISPLAY already set
# (a real X server, ssh -X) it uses that one and skips Xvfb.
set -eu
APP=$1 OUT=$2
shift 2
XV=
if [ -z "${DISPLAY:-}" ]; then
  export DISPLAY=:77
  Xvfb :77 -screen 0 1024x768x24 -nolisten tcp >/dev/null 2>&1 &
  XV=$!
  sleep 1
fi
"../$APP-linux" --live ${LIVEARGS:-} > "$OUT.log" 2>&1 &   # LIVEARGS: explorer's --sys/--regbox/--screen
P=$!
W=
for i in $(seq 50); do W=$(xdotool search --name "Windows 2000" 2>/dev/null | head -1) && [ -n "$W" ] && break; sleep 0.2; done
[ -n "$W" ] || { echo "no window"; cat "$OUT.log"; kill $P; [ -n "$XV" ] && kill $XV; exit 1; }
sleep 2
for s in "$@"; do
  case "$s" in
    shot\ *) xwd -silent -id "$W" | convert xwd:- "${OUT}_${s#shot }.png"; echo "shot ${OUT}_${s#shot }.png" ;;
    sleep\ *) sleep "${s#sleep }" ;;
    *) eval xdotool "$s" ;;
  esac
done
kill $P 2>/dev/null || true
[ -n "$XV" ] && kill $XV
true
