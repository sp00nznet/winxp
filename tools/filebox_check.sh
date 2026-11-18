#!/bin/sh
# tools/filebox_check.sh: the guest's drives are the box (pcrecomp syscall32.c, PCRECOMP_FILEBOX).
# Windows 2000's own cmd.exe (lifted) lists and writes C:\ in a box under work/fbtest; the check
# fails unless the guest sees only the box's files, and nothing outside the box changed.
cd "$(dirname "$0")/.." || exit 1
B=work/fbtest; rm -rf $B; mkdir -p $B/C/inbox_dir; echo hi > $B/C/inbox_marker.txt
# the guest's PATH has C:\WINNT\system32, placeholders for cmd's search (the launch path starts the runner by name)
mkdir -p $B/C/WINNT/system32; : > $B/C/WINNT/system32/find.exe; : > $B/C/WINNT/system32/more.com; : > $B/C/WINNT/system32/cmd.exe
export PCRECOMP_GUEST_PATH='C:\WINNT\system32'
export MSYS_NO_PATHCONV=1 PCRECOMP_MUTE=1 PCRECOMP_FILEBOX="$(cygpath -w "$PWD/$B")"
run() { timeout 30 ./build/cmd.exe --mute -- /c "$1" 2>&1 | tr -d '\r' | grep -v '^\[' | grep -v 'lifted functions, entering' ; }
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
L=$(run 'dir /b C:\')
[ "$(echo "$L" | sort | tr '\n' ' ')" = "WINNT inbox_dir inbox_marker.txt " ] && ok "dir C:\\ lists only the box: $(echo $L)" || bad "dir C:\\: $L"
L=$(run 'dir /b C:\..\..\..')
echo "$L" | grep -qi "inbox_marker" && ok "C:\\..\\..\\.. stays at the box's C:\\" || bad "C:\\..: $L"
L=$(run 'dir /b D:\ G:\ \\?\GLOBALROOT\Device\HarddiskVolume1\ \\localhost\c$ \\?\UNC\localhost\c$')
[ -z "$(echo "$L" | grep -iv 'not find\|not found\|cannot find\|network\|denied\|incorrect\|invalid\|^$')" ] && ok "D:, G:, GLOBALROOT, UNC: nothing listed" || bad "other names listed: $L"
L=$(run 'cd'); [ "$L" = 'C:\' ] && ok "current directory C:\\" || bad "cd: $L"
run 'echo boxed> C:\new.txt' >/dev/null
[ "$(tr -d '\r ' < $B/C/new.txt 2>/dev/null)" = boxed ] && ok "C:\\new.txt written into the box" || bad "C:\\new.txt not in the box"
run 'echo x> G:\recomp\pc\win2000\build\fbtest_evil.txt' >/dev/null
[ ! -e build/fbtest_evil.txt ] && ok "a write to the host's G:\\...\\build: not written" || { rm -f build/fbtest_evil.txt; bad "wrote into build"; }
L=$(run 'dir /b C:\Windows\system32')
echo "$L" | grep -qi kernel32 && bad "host system32 listed" || ok "C:\Windows\system32: the box's, not the host's"
L=$(run 'dir /b G:\recomp\pc\win2000\work\rebased-shell')
echo "$L" | grep -qi kernel32 && bad "loader directory listed" || ok "loader directory: files only, not listed"
L=$(run 'ver'); echo "$L" | grep -q "Windows 2000" && ok "the loader still maps the lifted modules (ver)" || bad "ver: $L"
L=$(run 'dir /b C:\ | more' | grep -v '^$'); [ "$(echo "$L" | sort | tr '\n' ' ')" = "WINNT inbox_dir inbox_marker.txt new.txt " ] && ok "a pipe to the lifted more (child runners in the box): $(echo $L)" || bad "dir | more: $L"
L=$(run 'dir C:\'); echo "$L" | grep -q "2,684,354,560 bytes free" && ok "free space is the box's (2.5 GB of 4 GB)" || bad "free space: $(echo "$L" | tail -1)"
L=$(run 'cd C:\inbox_dir & set FBVAR=guestval & cmd /c "cd & echo %FBVAR%"' | grep -v '^ *$' | tr '\n' ' ')
[ "$(echo $L)" = 'C:\inbox_dir guestval' ] && ok "a child cmd gets the guest's directory and environment: $L" || bad "child env/cwd: $L"
run 'cd /d G:\recomp\pc\win2000\work\rebased-shell & echo x> fbtest_evil.txt' >/dev/null
[ ! -e work/rebased-shell/fbtest_evil.txt ] && ok "a write after cd into a loader directory: not written" || { rm -f work/rebased-shell/fbtest_evil.txt; bad "wrote into work/rebased-shell"; }
exit $fail
