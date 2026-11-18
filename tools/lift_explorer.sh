#!/bin/sh
# tools/lift_explorer.sh [ISO]: Windows XP's explorer and its module set (bases: tools/fetch_xp.sh),
# lifted into src/gen/ntexplorer and built as part DLLs (--target ntexplorer_parts), then XP's own
# COM classes into the registry box. tools/run_explorer.sh runs it.
R=work/rebased-shell
sh tools/fetch_xp.sh "$@" || exit 1
# the accessories' set (tools/lift_accessories.sh) and explorer's own
SET3="ntdll kernel32 msvcrt user32 gdi32 comctl32 shlwapi shell32 comdlg32 winmm winspool.drv rpcrt4 secur32 uxtheme imm32"
SET4="browseui crypt32 cryptui imagehlp msasn1 netapi32 ole32 oleaut32 shdocvw version wininet wintrust wldap32
 actxprxy clbcatq comres desk.cpl mpr msls31 mydocs riched20 setupapi usp10"
M=""; for m in $SET3 sxs/Microsoft.Windows.Common-Controls/comctl32.dll $SET4; do case $m in *.dll|*.drv|*.cpl) M="$M $R/$m";; *) M="$M $R/$m.dll";; esac; done
py -3 tools/lift.py ntexplorer $R/explorer.exe $M > work/lift_ntexplorer.log 2>&1 || { tail -3 work/lift_ntexplorer.log; exit 1; }
tail -1 work/lift_ntexplorer.log
cmd //d //c "$(cygpath -w "$PWD")\build.cmd --target rebuild_cache" >/dev/null 2>&1
cmd //d //c "$(cygpath -w "$PWD")\build.cmd --target ntexplorer_parts" > work/build_ntexplorer_parts.log 2>&1 || { grep -E " error|FAILED" work/build_ntexplorer_parts.log | head; exit 1; }
echo built ntexplorer_parts
py -3 tools/reginst.py 'xp\explorer' $R browseui shell32 shdocvw comctl32 mydocs
