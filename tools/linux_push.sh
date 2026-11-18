#!/bin/sh
# Copy what a Linux build needs to a scratch directory on a Linux box:
#   tools/linux_push.sh user@host /tmp/w2k-scratch [PCRECOMP checkout] [cmd|ntwinmine]
# HOST "local" fills DIR here instead (a path relative to the repo, e.g. work/linux: setup.ps1 -Linux),
# for copying to a Linux machine by hand and building there with ./setup.sh.
# The lifted C and the Windows 2000 files are yours and stay out of git;
# delete the scratch directory when done (ssh user@host rm -rf DIR).
set -eu
HOST=$1 DIR=$2 PCR=${3:-${PCRECOMP:-../pcrecomp}} APP=${4:-cmd}
cd "$(dirname "$0")/.."
on() { if [ "$HOST" = local ]; then sh -c "$1"; else ssh "$HOST" "$1"; fi; }
on "mkdir -p '$DIR/root/sys' '$DIR/src' '$DIR/gen' '$DIR/pcrecomp/runtime'"
tar cf - -C src/gen "$APP" | on "tar xf - -C '$DIR/gen'"
tar cf - -C "$PCR/runtime" recomp32/recomp_types.h native32/ntposix.c native32/ntposix.h \
    native32/w32klayout.c native32/w32klayout.h native32/w32kposix.c native32/w32kposix.h | on "tar xf - -C '$DIR/pcrecomp/runtime'"
tar cf - src/nthost_linux.c -C tools linux_build.sh | on "tar xf - -C '$DIR' && mv '$DIR/src/linux_build.sh' '$DIR/' 2>/dev/null; true"
if [ -d "src/gen/$APP/explorer" ]; then
  # the shell: the Win11 explorer set's modules, Windows 2000's advapi32, the registry box
  # (tools/regbox_lx.py, at DIR/explorer.box) and the private profile under the guest's C:\
  tar cf - -C work/rebased-shell explorer.exe ntdll.dll kernel32.dll msvcrt.dll user32.dll gdi32.dll comctl32.dll \
      shlwapi.dll shell32.dll browseui.dll shdocvw.dll ole32.dll oleaut32.dll rpcrt4.dll actxprxy.dll clbcatq.dll \
      mydocs.dll url.dll -C ../lx/reb advapi32.dll | on "mkdir -p '$DIR/sys-ex' && tar xf - -C '$DIR/sys-ex'"
  # explorer's own --sys (DIR/sys-ex, its C:\WINNT\system32): the shell set's ntdll..gdi32 are not the
  # GUI set's that a launched NAME-linux maps from root/sys. ~clbcatq.dll is Windows 2000's own "no
  # COM+ catalog" marker (ole32 checks System32\~CLBCATQ.DLL; it is never loaded): ole32 takes the
  # registry, as on Windows (docs/linux.md). winmine.exe ... are Windows 2000's own files, as data: Run's
  # search and the Start menu's shortcuts resolve them, and their icons come from them. The launch path
  # starts ./winmine-linux, never a file.
  on ": > '$DIR/sys-ex/~clbcatq.dll'"
  tar cf - -C work/sys winmine.exe notepad.exe calc.exe sol.exe freecell.exe mspaint.exe wordpad.exe | on "tar xf - -C '$DIR/sys-ex'"
  tar cf - -C work/lx explorer.box | on "tar xf - -C '$DIR'"
  tar cf - -C work/profile/C "Documents and Settings" | on "mkdir -p '$DIR/root/TEMP' && tar xf - -C '$DIR/root'"
  TT=$(cd work/fonts && ls lucon.ttf tahoma.ttf marlett.ttf 2>/dev/null || true)
  tar cf - -C work/names win32k_2000sp4.txt -C ../fonts sserife.fon vgasys.fon $TT | on "tar xf - -C '$DIR/sys-ex'"
  tar cf - -C work/sys c_1252.nls c_437.nls l_intl.nls unicode.nls locale.nls ctype.nls sortkey.nls sorttbls.nls sortkey_00000409.nls | on "tar xf - -C '$DIR/sys-ex'"
elif [ "$APP" = cmd ]; then
  tar cf - -C work/rebased cmd.exe ntdll.dll kernel32.dll msvcrt.dll | on "tar xf - -C '$DIR/root/sys'"
else
  # stage 3: the GUI set, the win32k names, Windows 2000's bitmap fonts (expanded from the CD's .FO_)
  CARDS=; [ -d "src/gen/$APP/cards" ] && CARDS=cards.dll
  EXE=${APP#nt}; EXE=${EXE%_lx}
  [ -d "src/gen/$APP/mfc42u" ] && CARDS="$CARDS mfc42u.dll"
  [ -d "src/gen/$APP/riched20" ] && CARDS="$CARDS riched20.dll"
  [ -d "src/gen/$APP/comctl32" ] && tar cf - -C work/lx/reb comctl32.dll | on "tar xf - -C '$DIR/root/sys'"
  tar cf - -C work/rebased-gui "$EXE.exe" $CARDS ntdll.dll kernel32.dll msvcrt.dll user32.dll gdi32.dll | on "tar xf - -C '$DIR/root/sys'"
  # the TrueType faces w32kposix rasterizes (expand.exe from the CD's LUCON.TT_, TAHOMA.TT_), when there
  TT=$(cd work/fonts && ls lucon.ttf tahoma.ttf marlett.ttf 2>/dev/null || true)
  tar cf - -C work/names win32k_2000sp4.txt -C ../fonts sserife.fon vgasys.fon $TT | on "tar xf - -C '$DIR/root/sys'"
fi
tar cf - -C work/sys c_1252.nls c_437.nls l_intl.nls unicode.nls locale.nls ctype.nls sortkey.nls sorttbls.nls sortkey_00000409.nls | on "tar xf - -C '$DIR/root/sys'"
echo "pushed $APP to $HOST:$DIR"
