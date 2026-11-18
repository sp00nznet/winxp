#!/bin/sh
# Lift and build ntexplorer (explorer.exe and the shell's DLLs, rebased into work/rebased-gui)
R=work/rebased-shell
# Control Panel's applets (Date/Time, Display, Mouse/Keyboard) and what they import, Windows 2000's own,
# expanded from the CD into work/cplx and rebased here; devmgr.dll is our stand-in (src/stub/devmgr.c)
if [ ! -f $R/mpr.dll ]; then
  mkdir -p work/cplx; for f in TIMEDATE.CP_ MAIN.CP_ IMM32.DL_ COMDLG32.DL_ MPR.DL_; do 7z e -y -owork/cplx work/iso/I386/$f >/dev/null; done
  py -3 "${PCRECOMP:-../pcrecomp}"/tools/pe/rebase.py work/cplx $R timedate.cpl=0x21700000 imm32.dll=0x21800000 main.cpl=0x21900000 \
    comdlg32.dll=0x21A00000 mpr.dll=0x21B00000 || exit 1
fi
# Windows 2000's imagehlp (rundll32.exe imports it; the host's was proxied in before)
[ -f $R/imagehlp.dll ] || py -3 "${PCRECOMP:-../pcrecomp}"/tools/pe/rebase.py work/iso/I386 $R IMAGEHLP.DLL=0x21D00000 || exit 1
[ -f $R/devmgr.dll ] || cmd //d //c "$(cygpath -w "$PWD")\tools\devmgr_stub.cmd $(cygpath -w "$PWD/$R")" || exit 1
py -3 tools/lift.py ntexplorer $R/explorer.exe $R/ntdll.dll $R/kernel32.dll $R/msvcrt.dll $R/user32.dll $R/gdi32.dll \
  $R/comctl32.dll $R/shlwapi.dll $R/shell32.dll $R/browseui.dll $R/shdocvw.dll $R/ole32.dll $R/oleaut32.dll $R/rpcrt4.dll $R/actxprxy.dll $R/desk.cpl $R/clbcatq.dll $R/mydocs.dll \
  $R/timedate.cpl $R/imm32.dll $R/main.cpl $R/comdlg32.dll $R/mpr.dll $R/devmgr.dll \
  > work/lift_ntexplorer.log 2>&1 || { tail -3 work/lift_ntexplorer.log; exit 1; }
tail -1 work/lift_ntexplorer.log
cmd //d //c "$(cygpath -w "$PWD")\build.cmd --target ntexplorer" > work/build_ntexplorer.log 2>&1 || { grep -E "error|FAILED" work/build_ntexplorer.log | head; exit 1; }
echo built
# Windows 2000's own COM classes into explorer's registry box (with a lifted ole32 the host's are not answered)
py -3 tools/reginst.py 'w2k\explorer' $R browseui shell32 shdocvw comctl32 mydocs
# url.dll as a file (its icons, for the URL protocols' DefaultIcon): never mapped as code
[ -f $R/url.dll ] || 7z e -y -o$R work/iso/I386/URL.DL_ >/dev/null
# rundll32 on the same modules (Control Panel's applets: shell32 starts "rundll32 shell32.dll,Control_RunDLL x.cpl";
# the launch path runs build\ntrundll32.exe). rundll32.exe has no relocations: its own lift at 0x01000000
[ -f $R/rundll32.exe ] || 7z e -y -o$R work/iso/I386/RUNDLL32.EX_ >/dev/null
py -3 tools/lift.py ntrundll32 $R/rundll32.exe $R/ntdll.dll $R/kernel32.dll $R/msvcrt.dll $R/user32.dll $R/gdi32.dll \
  $R/comctl32.dll $R/shlwapi.dll $R/shell32.dll $R/browseui.dll $R/shdocvw.dll $R/ole32.dll $R/oleaut32.dll $R/rpcrt4.dll $R/actxprxy.dll $R/desk.cpl $R/clbcatq.dll $R/mydocs.dll \
  $R/timedate.cpl $R/imm32.dll $R/main.cpl $R/comdlg32.dll $R/mpr.dll $R/devmgr.dll $R/imagehlp.dll \
  > work/lift_ntrundll32.log 2>&1 || { tail -3 work/lift_ntrundll32.log; exit 1; }
cmd //d //c "$(cygpath -w "$PWD")\build.cmd --target rebuild_cache" >/dev/null 2>&1   # (a new lift's target)
cmd //d //c "$(cygpath -w "$PWD")\build.cmd --target ntrundll32" > work/build_ntrundll32.log 2>&1 || { grep -E "error|FAILED" work/build_ntrundll32.log | head; exit 1; }
echo built ntrundll32
