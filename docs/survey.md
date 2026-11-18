# Survey: Windows XP against the Windows 2000 runtime

Source: Windows XP Media Center Edition 2005 SP3 (`VRMHOEM_EN.ISO`, I386),
NT 5.1 build 2600, file versions 5.1.2600.5512. No plain XP Pro/Home ISO
was available; MCE's I386 core (ntdll, kernel32, user32, gdi32, cmd, the
accessories) is XP Pro SP3's.

Numbers below were read off this ISO's own files (`tools/svctable.py`,
`tools/disas.py`), not from symbols.

## Handoff (current state)

- pcrecomp branch `xp` (worktree ../pcrecomp-xp), rebased on main; every XP answer is behind the
  guest's build number (`runtime/native32/ntguest.h`, csr32.c's SxS section).
- Lift sets: `work/set3.txt` (accessories: XP's system DLLs, uxtheme, imm32 and comctl32 6.0 from
  `work/rebased-shell/sxs/Microsoft.Windows.Common-Controls/`, the SxS store the host names in
  PCRECOMP_SXS), `work/set4.txt` (+ explorer's, bases in `work/explorer_bases.txt`: 0x23000000 up,
  and actxprxy, clbcatq, comres, desk.cpl, mpr, msls31, mydocs, riched20, setupapi, usp10 at 0x24000000 up).
- `work/it.sh APP` relifts ntAPP on set3 and runs it; `work/rv.sh TARGET SECS` builds and runs.
- comctl32 6.0 now runs as itself. The "SysLink registration failure" was not user32's: native32_map
  kept only a module's bare name, so the guest loader got the 5.82 image for 6.0's file and 6.0's
  DllMain never ran (pcrecomp efedf78). Also fixed on the way: XP's `push n; push table; call
  __SEH_prolog` frames (disasm32 seeds their __finally/filters, eh32 their __except resume points),
  XP's TEB batch layouts (PolyPatBlt, TextOut), basesrv 27's ActivationContextData is a PVOID* the
  server writes through, SHAREDINFO DefWindowSpecMsgs zeroed, XP's NtUserCallOneParam 0x26
  (GetCursorPos), native32 MAX_MODULES 32 -> 64.
- Gate: `py -3 tools/interact.py winmine notepad calc` (see the last run in the report below).
  Remaining v6 differences, NOT approved as goldens: text v6 draws (Static, the double-buffered
  Edit, buttons) comes out in the stock System font, bold; v6's statics show the & underline
  (keyboard cues on). Lead: v6's Edit never selects its font into its memory DC (gdi32
  SelectObject is never called for it) though WM_SETFONT arrives with a valid font; look at
  v6 Edit's paint path (memory DC from 0x22406A65) and how it gets ped->hFont.
- Explorer: CMake's ntexplorer is XP's set, built as part DLLs (`--target ntexplorer_parts`: one
  image is ~450 MB, CreateProcess error 308). `tools/run_explorer.sh` runs it with the strict
  host-module check (only advapi32 proxied, passes). It now gets through the loader and into
  explorer's WinMain; Shell_TrayWnd's WM_CREATE fails (CreateWindowEx -> last error 2) after COM
  catalog probes (C:\Windows\Registration\*.clb, emptyregdb.dat), so no desktop/taskbar yet.
  The box has XP's classes from `py -3 tools/reginst.py xp\explorer work/rebased-shell browseui
  shell32 shdocvw comctl32 mydocs` plus {C90250F3-4D7D-4991-9B69-A5C5BC1C2AE6} -> browseui by hand
  (XP registers it in code). Next: find which tray component fails (CTray::_OnCreate: start button,
  rebar/bandsite, tray notify, clock) -- NATIVE32_SYSCALLS=1 and PCRECOMP_REGTRACE=1 runs.
- Debugging recipe used here: probe lifted code by inserting fprintf(stderr) at `RECOMP_ENTER(0x..u)`
  or `L_xxxx:` in src/gen (relift to clean); Windows' Application event log (id 1000) gives the
  part DLL + offset of a host fault, `tools/faultline.sh ADDR build/ntexplorer_<mod>.dll`.
- Known gaps: calc's button text one ClearType level off stage 1; no publisher policy or COM
  sections in the activation contexts; the Linux host's layouts (w32klayout.h) are 2000's.

## 1. The system call stub

Windows 2000 (11 bytes + ret):

    B8 nn nn nn nn     mov  eax, N
    8D 54 24 04        lea  edx, [esp+4]
    CD 2E              int  2Eh
    C2 xx xx           ret  4n

XP SP2+ (12 bytes + ret), in ntdll, user32 and gdi32 alike:

    B8 nn nn nn nn     mov  eax, N
    BA 00 03 FE 7F     mov  edx, 7FFE0300h      ; KUSER_SHARED_DATA.SystemCall
    FF 12              call dword ptr [edx]     ; -> KiFastSystemCall: mov edx,esp; sysenter
    C2 xx xx           ret  4n

The host's shared page has no SystemCall pointer at +0x300 (Windows 10/11
keep QpcFrequency there), so the call cannot be followed. pcrecomp's lifter
turns the pair into the system call itself (`edx = esp + 4; recomp_syscall`),
the same contract Windows 2000's `lea edx,[esp+4]; int 2Eh` had; the
runtime's table builders read both forms (`runtime/native32/ntguest.h`).
`KiIntSystemCall` (`lea edx,[esp+8]; int 2Eh`) and the callback return
(`int 2Bh` in KiUserCallbackDispatcher) are as before.

## 2. The service table

284 NT services (Windows 2000 SP4: 248). Only 9 keep their number, so the
table is read from the guest's ntdll at start, as for Windows 2000, and
answered by name. New in XP: keyed events, debug objects, NtCreateProcessEx,
NtSuspend/ResumeProcess, boot entries, NtOpenProcessTokenEx/
NtOpenThreadTokenEx, NtRenameKey, NtSaveKeyEx, NtTraceEvent and others
(`py -3 tools/svctable.py work/sys/ntdll.dll ../win2000/work/sys/ntdll.dll`).
All but 4 have a host counterpart by name.

win32k: 667 XP SP3 names (j00ru's table, `tools/w32k_names.py "Windows XP"
SP3`), 634 stubs found in user32/gdi32 by the shape above.

## 3. csrss

The CSR_API_MSG header is unchanged (data at +0x28). basesrv's
NlsGetUserInfo is api 30 on XP (26 on Windows 2000, where 30 is something
else): csr32.c registers the number for the guest's build at connect.
BASE_STATIC_SERVER_DATA as handed out for Windows 2000 is enough for XP's
kernel32 to finish its DllMain.

## 4. win32k shared state

| | Windows 2000 SP4 | XP SP3 |
|---|---|---|
| GDI handle table | 0x4000 x 16 B, DEVCAPS at +0x40000 | 0x10000 x 16 B, DEVCAPS at +0x100000 (same entry and DEVCAPS layout) |
| WND spwndNext / Parent / Child / Owner | 0x2C / 0x30 / 0x34 / 0x38 | 0x2C / 0x34 / 0x38 / 0x3C (spwndPrev at 0x30) |
| WND rcWindow / rcClient | 0x3C / 0x4C | 0x40 / 0x50 |
| WND cbwndExtra | 0x88 | 0x8C |
| WND extra bytes | 0x98 | 0xA4 (pActCtx and one more before them) |
| WND state2 / style / fnid | 0x18 / 0x20 / 0x2A | unchanged |
| CLIENTINFO | TEB+0x6CC | TEB+0x6CC |

All of these are now version-gated in pcrecomp (`runtime/native32/ntguest.h`):
w32kuser.c and csr32.c keep Windows 2000's numbers and pass each through a
map that returns XP's for an XP guest. Read off XP's user32 the same way:

| | Windows 2000 SP4 | XP SP3 |
|---|---|---|
| SERVERINFO | atomSysClass 0x1A0, MBStrings 0x1DC, aiSysMet 0x59C, argbSystem 0x6E8 (29), ahbrSystem 0x75C, cxSysFont 0x800, hMsgFont 0x858, LOGPIXELS 0xE4A, PrefMask 0xE50 | +0x20, +0x24, +0x24, 0x7A0 (31), 0x81C, then +0xC8: 0x8C8, 0x920, 0xF12, 0xF18 |
| SHAREDINFO DefWindowMsgs | +0xE8 | +0x108 (awmControl has 31 entries) |
| KernelCallbackTable | __fnDWORD 2, INCNTOUTSTRING 7, INLPCREATESTRUCT 9, INSTRING 25, ClientLoadMenu 65, ClientThreadSetup 74 | 2, 8, 10, 26, 67, 76 (one entry more at 3, another near 63) |
| NtUserCall* routine numbers | e.g. CallOneParam MessageBeep 0x24 | 0x31; 45 anchors read off the exports that pass them (tools: the same scan as work/routines.py), interpolated between equal shifts |
| FNIDs | DIALOG 0x2A2, SENDMESSAGE 0x2AE | 0x2A4, 0x2B0 (+2 from the controls on) |
| PFNCLIENT DispatchClientMessage | DefDlgProc + 0x24 | + 0x28 (pfnGhostWndProc before it) |
| win32k argument lists | NtUserCreateWindowEx 13, NtUserRegisterClassExWOW 6 | 15, 7: a class-version name after the class name (dropped for the 2000-shaped handlers); 5 others changed, unused so far |
| TEB | | +0x1A8 ACTIVATION_CONTEXT_STACK, its FrameListCache (+0x1B4) an empty list from the kernel |
| csrss | | basesrv 27 BaseSrvSxsCreateActivationContext (shell32's DllMain asks for its manifest): refused for now |

Also: XP's DbgPrint checks NtQueryDebugFilterState (answered "no"), and its
dialog manager asks NtUserGetAtomName for its class (integer atoms are "#n").

## 5. What applies from the Windows 2000 runtime as-is

- native32 module mapping, the dispatch, seh32, the launch guard, regbox32
  (boxed under `HKCU\Software\pcrecomp\xp\<app>`), the FILEBOX.
- syscall32.c's overrides by name; nt_boot's PEB/TEB (NT 5.0 offsets are
  NT 5.1's for every field it sets). The guest version comes from ntdll's
  VS_FIXEDFILEINFO: 5.1.2600.
- csr32.c's connect and console info.
- Not yet: w32klayout.h's USER layouts for the Linux host (w32kposix), activation
  contexts (comctl32 v6 by manifest: XP's loader asks csrss/sxs for the
  process default context; nothing answers yet), uxtheme.
