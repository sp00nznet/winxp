#!/bin/sh
# tools/run_explorer.sh NAME [SECS] [hiddenrun args...]: ntexplorer on an 800x600 virtual screen, muted,
# on hiddenrun's private desktop; shots/exp/NAME_<t>.png and .log. $EXARGS go to ntexplorer.
# Fails (exit 1) if any host module other than the allowed proxies was mapped into the guest.
N=$1; S=${2:-20}; shift 2 2>/dev/null
mkdir -p shots/exp
export PCRECOMP_MUTE=1 W2K_SCREEN=${W2K_SCREEN:-800x600}
# a private Windows XP profile (tools/profile.py): never the host's Start Menu, Desktop or AppData
# inside the file box (pcrecomp syscall32.c): the guest's drives are work/profile/<letter>, C:\ is
# work/profile/C, and the guest sees these host paths as C:\Documents and Settings\..., C:\TEMP
B=$(cygpath -w "$PWD/work/profile"); D='Documents and Settings'
py -3 tools/profile.py 'xp\explorer' "work/profile/C/$D" "C:\\$D" >/dev/null || exit 1
mkdir -p work/profile/C/TEMP; P="$B\\C\\$D"
# names for cmd's program search (find, more: the launch path starts their runners)
mkdir -p work/profile/C/WINDOWS/system32; : > work/profile/C/WINDOWS/system32/find.exe; : > work/profile/C/WINDOWS/system32/more.com
for x in charmap clipbrd sndrec32 winhlp32; do : > work/profile/C/WINDOWS/system32/$x.exe; done
# a help file for winhlp32 (Windows XP's Character Map help, from the CD)
mkdir -p work/profile/C/WINDOWS/Help; [ -f work/profile/C/WINDOWS/Help/charmap.hlp ] || 7z e -y -owork/profile/C/WINDOWS/Help work/iso/I386/CHARMAP.HL_ >/dev/null
export PCRECOMP_GUEST_PATH='C:\WINDOWS\system32'
# Windows XP's C:\Program Files\Internet Explorer\iexplore.exe, as a file: the folder window's
# frame takes its icon from it (htmlfile's DefaultIcon). Never run; the launch path starts only lifted exes.
IE="work/profile/C/Program Files/Internet Explorer"
[ -f "$IE/IEXPLORE.EXE" ] || { mkdir -p "$IE"; 7z e -y -o"$IE" work/iso/I386/IEXPLORE.EX_ >/dev/null; }
# Windows XP's look (tools/profile.py luna): the Luna visual style, loaded as data by the lifted uxtheme,
# and the Bliss wallpaper (the CD's bliss.jpg as the BMP win32k paints: pcrecomp w32kuser.c)
TH="work/profile/C/WINDOWS/Resources/Themes/Luna"; WP="work/profile/C/WINDOWS/Web/Wallpaper"
[ -f "$TH/luna.msstyles" ] || { mkdir -p "$TH" && 7z e -y -o"$TH" work/iso/I386/LUNA.MS_ >/dev/null; [ ! -f "$TH/luna.mst" ] || mv -f "$TH/luna.mst" "$TH/luna.msstyles"; }   # (7-Zip 9 keeps 8.3: luna.mst)
[ -f "$WP/Bliss.bmp" ] || { mkdir -p "$WP" && 7z e -y -o"$WP" work/iso/I386/BLISS.JP_ >/dev/null &&
  powershell -NoProfile -Command "Add-Type -AssemblyName System.Drawing; \$i=[Drawing.Image]::FromFile('$(cygpath -w "$WP/bliss.jpg")'); \$i.Save('$(cygpath -w "$WP/Bliss.bmp")', [Drawing.Imaging.ImageFormat]::Bmp); \$i.Dispose()" &&
  rm -f "$WP/bliss.jpg"; }
export ProgramFiles="$B\\C\\Program Files" CommonProgramFiles="$B\\C\\Program Files\\Common Files" ProgramW6432= CommonProgramW6432=
export USERPROFILE="$P\\user" ALLUSERSPROFILE="$P\\all" ProgramData="$P\\all" PUBLIC="$P\\all" \
  APPDATA="$P\\user\\Application Data" LOCALAPPDATA="$P\\user\\Local Settings\\Application Data" \
  HOMEDRIVE= HOMEPATH= TEMP="$B\\C\\TEMP" TMP="$B\\C\\TEMP" PCRECOMP_FILEBOX="$B"
py -3 tools/hiddenrun.py --secs "$S" --shot $((S - 3)) --out shots/exp/$N "$@" -- "$(cygpath -m "$PWD")/build/ntexplorer.exe" --mute --watchdog $((S - 1)) $EXARGS | tail -${TAIL_SHOWN:-2}
grep -v "HOST DLL in the guest: .*advapi32.dll" shots/exp/$N.log | grep -v "RegisterClassExW .* failed: 1410" | head -${LINES_SHOWN:-40}
# ponytail: advapi32 is the only host DLL explorer may proxy; widen ALLOW when a new one is reviewed
ALLOW='advapi32\.dll'
# every process in the run, launched children included, from its first line: the same rule for all
BAD=$(grep -aiE "HOST DLL in the guest|the host.s, through a proxy" shots/exp/$N.log | grep -aivE "[\\\\/]($ALLOW)[,:]")
[ -z "$BAD" ] || { echo "!!! HOST MODULE IN THE GUEST (run failed):"; echo "$BAD"; exit 1; }
