#!/bin/sh
# tools/lift_accessories.sh [APP...]: the accessories (default winmine notepad calc) on XP's own set:
# its system DLLs, uxtheme, imm32 and comctl32 6.0 (the SxS store, PCRECOMP_SXS). cmd on ntdll..gdi32.
R=work/rebased-shell
sh tools/fetch_xp.sh || exit 1
U="$R/ntdll.dll $R/kernel32.dll $R/msvcrt.dll $R/user32.dll $R/gdi32.dll"
SET3="$U $R/comctl32.dll $R/shlwapi.dll $R/shell32.dll $R/comdlg32.dll $R/winmm.dll $R/winspool.drv $R/rpcrt4.dll
 $R/secur32.dll $R/uxtheme.dll $R/imm32.dll $R/sxs/Microsoft.Windows.Common-Controls/comctl32.dll"
for app in ${@:-winmine notepad calc}; do
  case $app in cmd) T=cmd; M="$R/cmd.exe $U";; *) T=nt$app; M="$R/$app.exe $SET3";; esac
  py -3 tools/lift.py $T $M > work/lift_$T.log 2>&1 || { tail -3 work/lift_$T.log; exit 1; }
  cmd //d //c "$(cygpath -w "$PWD")\build.cmd --target rebuild_cache" >/dev/null 2>&1
  cmd //d //c "$(cygpath -w "$PWD")\build.cmd --target $T" > work/build_$T.log 2>&1 || { grep -E " error|FAILED" work/build_$T.log | head; exit 1; }
  echo "built $T: $(tail -1 work/lift_$T.log)"
done
