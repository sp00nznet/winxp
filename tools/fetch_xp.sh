#!/bin/sh
# tools/fetch_xp.sh [ISO]: Windows XP's files from the CD into work/sys and the rebased set in
# work/rebased-shell (each module at its own fixed base), the comctl32 6.0 SxS assembly in
# work/rebased-shell/sxs/. Needs work/iso/I386 (7z x -owork/iso ISO "I386/*", done here if ISO given).
# Idempotent; R=DIR to write elsewhere (a check that a fresh clone gets the same bytes).
P=${PCRECOMP:-../pcrecomp}; R=${R:-work/rebased-shell}; I=work/iso/I386; S=work/sys
[ -n "$1" ] && [ ! -d $I ] && { 7z x -y -owork/iso "$1" "I386/*" >/dev/null || exit 1; }
[ -d $I ] || { echo "no $I: tools/fetch_xp.sh <XP CD image>"; exit 1; }
mkdir -p $S $R
x() { for f; do [ -f $I/$f ] && { cp $I/$f $S/; continue; }; 7z e -y -o$S "$I/${f%?}_" >/dev/null || exit 1; done; }
# the modules and their bases (0x20000000 up: system; 0x23000000 up: explorer's set; 0x24000000 up: explorer's extras)
BASES="ntdll.dll=0x20000000 kernel32.dll=0x20100000 msvcrt.dll=0x20200000 user32.dll=0x20300000 gdi32.dll=0x20400000
 comctl32.dll=0x20800000 shlwapi.dll=0x20900000 shell32.dll=0x21000000 comdlg32.dll=0x21A00000 winmm.dll=0x21E00000
 winspool.drv=0x21F00000 rpcrt4.dll=0x22000000 secur32.dll=0x22100000 uxtheme.dll=0x22600000 imm32.dll=0x22700000
 browseui.dll=0x23000000 crypt32.dll=0x23100000 cryptui.dll=0x23200000 imagehlp.dll=0x23300000 msasn1.dll=0x23400000
 netapi32.dll=0x23500000 ole32.dll=0x23600000 oleaut32.dll=0x23800000 shdocvw.dll=0x23900000 version.dll=0x23B00000
 wininet.dll=0x23C00000 wintrust.dll=0x23D00000 wldap32.dll=0x23E00000
 actxprxy.dll=0x24000000 clbcatq.dll=0x24100000 desk.cpl=0x24300000 mpr.dll=0x24400000 msls31.dll=0x24500000
 mydocs.dll=0x24600000 riched20.dll=0x24700000 setupapi.dll=0x24800000 usp10.dll=0x24900000 comres.dll=0x24A00000"
EXES="explorer.exe notepad.exe calc.exe winmine.exe cmd.exe"
NEED=""; for b in $BASES; do f=${b%%=*}; [ -f $R/$f ] || NEED="$NEED $b"; done
NX=""; for e in $EXES; do [ -f $R/$e ] || NX="$NX $e"; done
U() { echo "$1" | tr a-z A-Z; }
for b in $NEED; do x $(U ${b%%=*}); done; for e in $NX; do x $(U $e); done
# the NLS tables kernel32 reads
x C_1252.NLS C_437.NLS L_INTL.NLS UNICODE.NLS LOCALE.NLS CTYPE.NLS SORTKEY.NLS SORTTBLS.NLS
( cd $S && for f in *; do l=$(echo "$f" | tr A-Z a-z); [ "$f" = "$l" ] || mv -f "$f" "$l"; done )
[ -z "$NEED" ] || py -3 $P/tools/pe/rebase.py $S $R $NEED >/dev/null || exit 1
for e in $NX; do py -3 $P/tools/pe/rebase.py $S $R $e >/dev/null || exit 1; done
# comctl32 6.0 (XP SP3's 6.0.2600.5512, the ASMS/60 assembly), the store PCRECOMP_SXS names
A=$R/sxs/Microsoft.Windows.Common-Controls; C=$I/ASMS/60/MSFT/WINDOWS/COMMON/CONTROLS
if [ ! -f $A/comctl32.dll ]; then
  mkdir -p $A work/sxsin; cp $C/COMCTL32.DLL work/sxsin/comctl32.dll
  py -3 $P/tools/pe/rebase.py work/sxsin $A comctl32.dll=0x22400000 >/dev/null || exit 1
  cp $C/CONTROLS.MAN $A/Microsoft.Windows.Common-Controls.manifest
fi
echo "fetched: $R"
