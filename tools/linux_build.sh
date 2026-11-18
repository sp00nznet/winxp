#!/bin/sh
# Build a Linux host on pcrecomp's POSIX NT backend (runtime/native32/ntposix.c):
#   sh linux_build.sh            cmd-linux: cmd.exe + msvcrt + kernel32 + ntdll
#   sh linux_build.sh ntwinmine  winmine-linux: + user32 + gdi32, win32k in w32kposix.c
# Run on the Linux box, in the scratch directory tools/linux_push.sh fills:
#   gen/APP/...  pcrecomp/runtime/...  src/nthost_linux.c
# Needs gcc with -m32 (Debian: gcc-multilib). docs/linux.md.
set -eu
cd "$(dirname "$0")"
APP=${1:-cmd}
J=${J:-$(nproc)}
DEFS="-DRECOMP_RETADDR=0u -DRECOMP_FLAT_MEMORY -DRECOMP_LOCAL_REGS"
INC="-Ipcrecomp/runtime/recomp32 -Ipcrecomp/runtime/native32 -Igen/$APP"
CF="-m32 -fno-strict-aliasing -fwrapv -fno-pie $DEFS $INC"
O=obj/$APP
mkdir -p "$O"
# the lifted C, unoptimised (as pcrecomp_gen.cmake does; recomp_part.c, a part DLL's table, is left out there too)
find "gen/$APP" -name '*.c' ! -name recomp_part.c | while read -r f; do
  o=$O/$(echo "$f" | tr / _ | sed 's/\.c$/.o/')
  [ "$o" -nt "$f" ] || echo "$f $o"
done | xargs -r -P "$J" -n 2 sh -c 'gcc '"$CF"' -O0 -w -c "$0" -o "$1"'
HOST="$CF -O1 -g -Wall -Wno-unused-function"
N=pcrecomp/runtime/native32
if [ "$APP" = cmd ]; then
  gcc $HOST -c $N/ntposix.c -o obj/ntposix.o
  gcc $HOST -c src/nthost_linux.c -o obj/nthost_cmd.o
  gcc -m32 -no-pie "$O"/*.o obj/ntposix.o obj/nthost_cmd.o -lpthread -lm -o cmd-linux
  echo "built ./cmd-linux"
else
  EXE=${APP#nt}; EXE=${EXE%_lx}                 # (ntmspaint_lx: mspaint's Linux set, with comctl32)
  gcc $HOST -c $N/ntposix.c -o obj/ntposix.o
  gcc $HOST -c $N/w32klayout.c -o obj/w32klayout.o
  X=; LX=; [ -e /usr/lib/i386-linux-gnu/libX11.so ] && X=-DW2K_X11 LX=-lX11   # --live
  gcc $HOST $X -c $N/w32kposix.c -o obj/w32kposix.o
  CARDS=; [ -d "gen/$APP/cards" ] && CARDS=-DW2K_CARDS
  [ -d "gen/$APP/mfc42u" ] && CARDS="$CARDS -DW2K_MFC"
  [ -d "gen/$APP/riched20" ] && CARDS="$CARDS -DW2K_RICHED"
  [ -d "gen/$APP/explorer" ] && CARDS="$CARDS -DW2K_EXPLORER"
  gcc $HOST -DW2K_GUI $CARDS "-DW2K_EXE=\"$EXE.exe\"" -c src/nthost_linux.c -o obj/nthost_$EXE.o
  gcc -m32 -no-pie "$O"/*.o obj/ntposix.o obj/w32klayout.o obj/w32kposix.o obj/nthost_$EXE.o $LX -lpthread -lm -o "$EXE-linux"
  echo "built ./$EXE-linux"
fi
