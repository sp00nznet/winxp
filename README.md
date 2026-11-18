# winxp-recomp

Windows XP's own userland, statically recompiled with
[pcrecomp](https://github.com/sp00nznet/pcrecomp) and run as ordinary
programs on a modern Windows host, with no emulator. The sibling of
[win2000-recomp](https://github.com/sp00nznet/win2000-recomp), and built on
the same runtime: XP-specific answers live in pcrecomp behind a check of the
guest's own build number, so Windows 2000 keeps working on the same toolkit.

**This repository contains no Windows code or data.** You lift your own copy
of Windows XP; everything that comes from it (extracted files, catalogs,
lifted C) goes into the gitignored `work/` and `src/gen/`. No product key is
needed or read.

How it works: [docs/survey.md](docs/survey.md) (what differs from Windows
2000) and win2000-recomp's docs/architecture.md (the design both share).

## Status

Source used: Windows XP Media Center Edition 2005 SP3 CD (NT 5.1.2600.5512).

| Stage | What | State |
|---|---|---|
| 1 | Stock accessories lifted on native32 against the host's DLLs | winmine, notepad, calc run |
| 2 | XP's own ntdll + kernel32 + msvcrt (+ user32/gdi32 mapped) lifted, started by ntdll's LdrInitializeThunk; system calls through XP's `call [7FFE0300h]` stubs | `cmd /c ver` prints `Microsoft Windows XP [Version 5.1.2600]`; echo, dir (of the file box), set, if, for |
| 3 | XP's own user32/gdi32 (and shell32, comctl32 5.82, comdlg32, winmm, ...) lifted, on pcrecomp's win32k layer with XP's layouts (docs/survey.md, section 4) | `tools/interact.py`: winmine (start, click, Intermediate, Custom 20x30, menus) and notepad (start, typed) pixel-identical to stage 1, 9/9 states; calc runs and computes, 864 px off on its button text (one ClearType level) |
| explorer | | not yet |

## Building by hand

Prerequisites as win2000-recomp's (Visual Studio 2022 x86 tools, CMake,
Ninja, Python 3 with pefile and capstone, 7-Zip, Git for Windows), and a
pcrecomp checkout at `../pcrecomp` or `PCRECOMP=...` with the XP support.

1. Extract I386 and expand the files:

   ```
   7z x -owork\iso <your XP CD image> "I386/*"
   7z e -owork\sys work\iso\I386\WINMINE.EX_ work\iso\I386\NOTEPAD.EX_ work\iso\I386\CALC.EX_
   7z e -owork\sys work\iso\I386\CMD.EX_ work\iso\I386\KERNEL32.DL_ work\iso\I386\MSVCRT.DL_ work\iso\I386\USER32.DL_ work\iso\I386\GDI32.DL_
   copy work\iso\I386\NTDLL.DLL work\sys\ntdll.dll
   7z e -owork\sys work\iso\I386\C_1252.NL_ work\iso\I386\C_437.NL_ work\iso\I386\L_INTL.NL_ work\iso\I386\UNICODE.NL_ work\iso\I386\LOCALE.NL_ work\iso\I386\CTYPE.NL_ work\iso\I386\SORTKEY.NL_ work\iso\I386\SORTTBLS.NL_
   ```

2. Stage 1: `py -3 tools\lift.py winmine work\sys\winmine.exe` (notepad,
   calc likewise), `build.cmd`.

3. Stage 2: win32k's names (`work/names/win32k-per-system.json` from
   github.com/j00ru/windows-syscalls, then
   `py -3 tools\w32k_names.py "Windows XP" SP3 > work\names\win32k.txt`),
   then rebase and lift:

   ```
   py -3 ..\pcrecomp\tools\pe\rebase.py work\sys work\rebased-shell ntdll.dll=0x20000000 kernel32.dll=0x20100000 msvcrt.dll=0x20200000 user32.dll=0x20300000 gdi32.dll=0x20400000
   py -3 ..\pcrecomp\tools\pe\rebase.py work\sys work\rebased-shell cmd.exe
   py -3 tools\lift.py cmd work\rebased-shell\cmd.exe work\rebased-shell\ntdll.dll work\rebased-shell\kernel32.dll work\rebased-shell\msvcrt.dll work\rebased-shell\user32.dll work\rebased-shell\gdi32.dll
   build.cmd --target cmd
   ```

Run everything muted, on a private desktop, in the file box:

```
set PCRECOMP_MUTE=1
set HIDDENRUN_DESKTOP=pcrecomp_xp
set PCRECOMP_FILEBOX=%CD%\work\profile
py -3 tools\hiddenrun.py --secs 15 --out shots\ver -- build\cmd.exe --mute --watchdog 12 -- /c ver
```

A run that faults names the function it could not find
(`ICALL: unresolved`): `sh tools/seed.sh shots\ver.log` records it for the
next lift.

## License

MIT (this repository's scripts and host code only).
