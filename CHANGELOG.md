# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[SemVer](https://semver.org/).

## [Unreleased]

### Changed
- README in the house order (Getting Started with the installer, Status,
  Screenshots, Documentation, License); CHANGELOG.md, ROADMAP.md and
  CONTRIBUTING.md added.
- `tools/interact.py` takes `BUILD_DIR` (another build of the same tree), as
  win2000's does.

## [0.1.0] - 2026-11-20

### Added
- Stage 1: XP's winmine, notepad and calc lifted on native32 against the
  host's DLLs. Stage 2: cmd.exe on XP's own ntdll, kernel32 and msvcrt;
  `cmd /c ver` prints `Microsoft Windows XP [Version 5.1.2600]`.
- `tools/interact.py` and `tools/gdicmp.py` run the lifted builds in a file
  box.
- Stage 3: winmine and notepad on XP's own user32 and gdi32, pixel-identical
  to stage 1.
- comctl32 6.0 runs as itself, from the CD's side-by-side store.
- Reproducible from the CD: `tools/fetch_xp.sh` (files, bases, SxS) and the
  lift sets in `tools/`; browseui's code-registered class in `reginst.py`.
- Explorer's desktop, taskbar and Start menu, with XP's apphelp, winsta and
  userenv lifted too; `tools/pdbsyms.py` names a module's addresses from
  Microsoft's public symbols.
- `Setup.cmd` and `tools/setup.ps1`, tested from a clean clone (47 minutes,
  7.2 GB); the README with the hero GIF and shots from private-desktop runs.
- The guest's own identity: user `User` on computer `PCRECOMP`, at the
  console (no host name, no Disconnect); desktop icons, the Start logo, the
  clock, and Run → winmine.
- Luna and Bliss: XP's theme, colors, metrics and wallpaper set in the box
  only (`tools/profile.py`), `luna.msstyles` and `Bliss.bmp` expanded from
  the CD by `tools/run_explorer.sh`, the theme started before the entry
  point, and `interact.py` run in Luna.
- Approved goldens (3840x2160@192, Luna): winmine start, click and menu open,
  notepad start and typed.
- `tools/linux_push.sh` copies `native32/ntguest.h`.
- An installer for recomp-launcher: `launcher/launcher.json` and an installer
  workflow that attaches it to a `v*` tag's release; `-Iso` takes a folder
  holding the `.iso`.

### Changed
- The setup and README use pcrecomp's main, which has Luna since the `luna`
  branch was merged.
