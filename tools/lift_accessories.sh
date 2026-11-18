#!/bin/sh
# tools/lift_accessories.sh [APP...]: the accessories (and cards, MFC, RichEdit) on the shell's module set,
# every DLL they load lifted: Windows 2000's shell32, comdlg32, winmm, winspool, olecli32/olesvr32, nddeapi.
# A program explorer launches must not proxy a host DLL (run_explorer.sh's check covers every process).
R=work/rebased-shell
if [ ! -f $R/nddeapi.dll ]; then
  mkdir -p work/accx; for f in WINMM.DL_ WINSPOOL.DR_ OLECLI32.DL_ OLESVR32.DL_ NDDEAPI.DL_; do 7z e -y -owork/accx work/iso/I386/$f >/dev/null; done
  py -3 "${PCRECOMP:-../pcrecomp}"/tools/pe/rebase.py work/accx $R winmm.dll=0x21E00000 winspool.drv=0x21F00000 \
    olecli32.dll=0x22000000 olesvr32.dll=0x22100000 nddeapi.dll=0x22200000 || exit 1
fi
# cmd (MessageBeep, GetProcessWindowStation, ...) and ulib (CharUpperW, wsprintfA) import user32:
# lifted user32/gdi32 too, ulib moved off user32's 0x20300000
[ -f $R/ulib.dll ] || { mkdir -p work/accx; 7z e -y -owork/accx work/iso/I386/ULIB.DL_ >/dev/null;
  py -3 "${PCRECOMP:-../pcrecomp}"/tools/pe/rebase.py work/accx $R ulib.dll=0x22300000 || exit 1; }
# charmap (getuname), sndrec32 (msacm32), winhlp32: Windows 2000's, on the same set
if [ ! -f $R/msacm32.dll ]; then
  mkdir -p work/acc2; for f in CHARMAP.EX_ GETUNAME.DL_ SNDREC32.EX_ MSACM32.DL_ WINHLP32.EX_; do 7z e -y -owork/acc2 work/iso/I386/$f >/dev/null; done
  py -3 "${PCRECOMP:-../pcrecomp}"/tools/pe/rebase.py work/acc2 $R getuname.dll=0x22400000 msacm32.dll=0x22500000 || exit 1
  # each exe by itself through rebase.py: it drops their bound imports (msvcrt's, kernel32's linked addresses)
  for e in CharMap.exe sndrec32.exe winhlp32.exe; do d=work/acc2x_$e; mkdir -p $d; cp work/acc2/$e $d/
    py -3 "${PCRECOMP:-../pcrecomp}"/tools/pe/rebase.py $d $R $e=0x01000000 >/dev/null || exit 1; done
fi
for f in find.exe more.com; do [ -f $R/$f ] || cp work/rebased-util/$f $R/; done
[ -f $R/cmd.exe ] || cp work/rebased/cmd.exe $R/
# the programs and their own DLLs: the same files as work/rebased-gui
for f in winmine.exe notepad.exe calc.exe clipbrd.exe packager.exe sol.exe freecell.exe mspaint.exe wordpad.exe cards.dll mfc42u.dll riched20.dll; do
  [ -f $R/$f ] || cp work/rebased-gui/$f $R/
done
SHELL_MODS="$R/ntdll.dll $R/kernel32.dll $R/msvcrt.dll $R/user32.dll $R/gdi32.dll $R/comctl32.dll $R/shlwapi.dll $R/shell32.dll \
  $R/browseui.dll $R/shdocvw.dll $R/ole32.dll $R/oleaut32.dll $R/rpcrt4.dll $R/actxprxy.dll $R/desk.cpl $R/clbcatq.dll $R/mydocs.dll \
  $R/timedate.cpl $R/imm32.dll $R/main.cpl $R/comdlg32.dll $R/mpr.dll $R/devmgr.dll \
  $R/winmm.dll $R/winspool.drv $R/olecli32.dll $R/olesvr32.dll $R/nddeapi.dll"
U="$R/ntdll.dll $R/kernel32.dll $R/msvcrt.dll $R/user32.dll $R/gdi32.dll"
for app in ${@:-winmine notepad calc clipbrd packager sol freecell mspaint wordpad cmd find more}; do
  case $app in
    cmd) T=cmd; M="$R/cmd.exe $U";;
    find) T=find; M="$R/find.exe $U $R/ulib.dll";;
    more) T=more; M="$R/more.com $U $R/ulib.dll";;
    sol|freecell) T=nt$app; M="$R/$app.exe $SHELL_MODS $R/cards.dll";;
    mspaint) T=nt$app; M="$R/$app.exe $SHELL_MODS $R/mfc42u.dll";;
    wordpad) T=nt$app; M="$R/$app.exe $SHELL_MODS $R/mfc42u.dll $R/riched20.dll";;
    charmap) T=nt$app; M="$R/$app.exe $SHELL_MODS $R/getuname.dll $R/riched20.dll";;   # (its font box: RichEdit)
    sndrec32) T=nt$app; M="$R/$app.exe $SHELL_MODS $R/msacm32.dll";;
    *) T=nt$app; M="$R/$app.exe $SHELL_MODS";;
  esac
  py -3 tools/lift.py $T $M > work/lift_$T.log 2>&1 || { tail -3 work/lift_$T.log; exit 1; }
  cmd //d //c "$(cygpath -w "$PWD")\build.cmd --target rebuild_cache" >/dev/null 2>&1   # (a new lift's target)
  cmd //d //c "$(cygpath -w "$PWD")\build.cmd --target $T" > work/build_$T.log 2>&1 || { grep -E " error|FAILED" work/build_$T.log | head; exit 1; }
  echo "built $T: $(tail -1 work/lift_$T.log)"
done
