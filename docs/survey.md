# Survey: Windows XP against the Windows 2000 runtime

Source: Windows XP Media Center Edition 2005 SP3 (`VRMHOEM_EN.ISO`, I386),
NT 5.1 build 2600, file versions 5.1.2600.5512. No plain XP Pro/Home ISO
was available; MCE's I386 core (ntdll, kernel32, user32, gdi32, cmd, the
accessories) is XP Pro SP3's.

Numbers below were read off this ISO's own files (`tools/svctable.py`,
`tools/disas.py`), not from symbols.

## Handoff (current state)

- pcrecomp branch `luna` (worktree ../pcrecomp-luna, on top of `xp`); every XP answer is behind the guest's build
  number (`runtime/native32/ntguest.h`; `build >= 2600` where the PEB is not filled yet).
- Reproducible from the CD: `tools/fetch_xp.sh` expands and rebases every module at its base
  (0x20000000 system, 0x23000000 explorer's set, 0x24000000 its extras: ... apphelp 0x24B00000,
  winsta 0x24C00000, userenv 0x24D00000) and comctl32 6.0 (ASMS/60) into
  `work/rebased-shell/sxs/`; `tools/lift_accessories.sh` (set3) and `tools/lift_explorer.sh`
  (set4) hold the module lists; reginst.py adds browseui's code-registered
  {C90250F3-...}. `Setup.cmd` / `tools/setup.ps1` run it all.
- **Explorer: desktop, taskbar and the Start menu show** (`tools/run_explorer.sh NAME 30`,
  strict host-module check passes; `--drag 30,588,30,588@15` opens Start). What it took
  (pcrecomp 7022606): HKLM `COM3` and `Explorer\Streams` box-only for XP (the host's COM3 sent
  clbcatq to Win11's REGDB: Shell_TrayWnd's WM_CREATE failed, error 2); an empty COM server
  redirection section in every activation context plus a system default context (PEB+0x200);
  CoRegisterClassObject retried in process only when INPROC|LOCAL_SERVER fails (no OXID
  resolver: CLSID_TaskBand never registered, so no bands and an 8 px taskbar); wnd_thunk holds
  the machine before touching g_fs_base (another thread's TEB got the CallbackWnd: a crash 4 s
  in); XP's apphelp, winsta, userenv lifted (they were host proxies).
- **comctl32 6.0's font: fixed** (pcrecomp, w32kgdi.c cb_in): XP's gdi32 selects fonts
  client-side, and the WM_CTLCOLOR* DC was re-entered from the host DC (stock font) over it.
  Calc's red/blue labels are calc's own colours (stage 1 on Win11's comctl32 draws them black).
- **Guest identity** (pcrecomp 5790c73): the guest is user `User` on `PCRECOMP`, at the console.
  regbox32.c: proxied advapi32 GetUserName A/W, GetUserNameExW, LookupAccountSid(Local) A/W,
  LsaLookupSids(2), LsaGetUserName, LsaQueryInformationPolicy (3/5/12) rewrite host names;
  NetWkstaGetInfo refused; the box is seeded with ComputerName/ActiveComputerName, Tcpip
  (NV) Hostname, Winlogon DefaultUserName/DomainName, RegisteredOwner, Volatile Environment
  USERNAME/USERDOMAIN/LOGONSERVER; any host registry value holding a host name (whole word)
  reads as absent. syscall32.c: the guest environment drops USERNAME/USERDOMAIN*/COMPUTERNAME/
  LOGONSERVER/SESSIONNAME/CLIENTNAME/USERDNSDOMAIN and any entry naming the host, then sets fixed
  ones. XP user32's remote test is PEB SessionId != KUSER ActiveConsoleId (0x7FFE02D8): an XP
  guest takes the console id (no "Disconnect", and the tray clock now shows);
  ProcessSessionInformation answers the PEB's. Pipes/UNC are refused by the file box (no wkssvc/
  lsarpc), LPC to LsaAuthenticationPort/IcaApi refused (WTS/winsta answer nothing).
  Gaps: NtEnumerateValueKey of host keys is not scrubbed; secur32 GetUserNameEx formats other
  than SamCompatible/Display fail when proxied. win2000's Start menu (classic) never showed it.
- Icons + Start logo: NtGdiAlphaBlend/NtGdiStretchBlt in w32kgdi.c (92aed60).
- Run -> winmine: `--childpost 'Shell_TrayWnd:0x111,0x191,0@10'`, WM_CHARs to 200,486,
  `--childpost '#32770:0x111,1,0@17'`; `[launch] ntwinmine`, verclsid.exe refused by the guard.
- Clean clone (2026-11-18): Setup.cmd -Yes 47 min, 7.2 GB; rerun 4 s (fetch/reginst/profile
  rerun idempotently); clone's run_explorer strict check passes, interact runs all 11 states
  (no stage 1 in a clone: "stage1 missing"). xp box exported/restored (same content).
- win2000 interact on build-xpcheck (after 92aed60), same hour as win2000 build/: every row equal (all golden 0; mspaint/wordpad stage1 6022/4894 on both) except winmine click 86 once on xp, 0 on rerun (the known flake).
- **Luna + Bliss** (pcrecomp luna): ThemeApiPort answered, uxtheme's own loader reads the CD's
  luna.msstyles (run_explorer.sh expands it and Bliss.bmp into work/profile; profile.py sets the
  theme/colours/metrics/wallpaper in the box only), user32 hooks installed as win32k's
  RegisterUserApiHook would, theme started before the entry point; DrawStream, regions,
  themed frame metrics, wallpaper in w32kgdi.c/w32kuser.c/csr32.c. Debug env switches removed.
- Gate (2026-11-18, 3840x2160@192, Luna): XP goldens approved for winmine start, click, menu
  open and notepad start, typed (all 0; click can tick the counter once: 86 px, 0 on rerun).
  Not approved (visible bugs): winmine intermediate/custom/custom 20x30/menu+Interm. (a strip
  of the old frame left after the resize), calc start/12+3= (window 260 wide vs 270: right
  column clipped). Those fail as NO GOLDEN until fixed.
- win2000 interact on build-xpcheck (pcrecomp-luna 4174395) vs build/, same hour: equal rows
  except sol deal/deck golden, packager stage1 and wordpad stage1/golden, which flip between
  the same values run to run on both builds (rerun twice each: timing, not the branch).
- Explorer stability: 1/15 died before (exit 5: shdocvw -> NetGetJoinInformation -> refused
  \pipe\wkssvc raised ERROR_ACCESS_DENIED into netapi32's RpcExcept, whose resume returned to
  0 from ntdll __SEH_epilog). pcrecomp native32_netapi_refuse answers NetGetJoinInformation/
  NetWkstaGetInfo/NetWkstaUserGetInfo ERROR_ACCESS_DENIED before the RPC: 15/15 clean after.
  The underlying seh32 resume-to-0 after a non-RPC_S code is not fixed.
- Next: the resize leftover strip and calc's width in Luna; Run dialog frame (classic), host-
  drawn popup menus, Start menu user picture and MFU list; the Start menu's program list.
- Debugging: `tools/pdbsyms.py MODULE > work/pdb/x.syms.txt` (MS public symbols, OMAP applied);
  `PCRECOMP_REGTRACE=2` (every box open), `PCRECOMP_FAULTTRACE=1` (guest stack + entry ring at
  a host AV), `PCRECOMP_TEXTTRACE=1` (batched text/fonts); probes by fprintf at RECOMP_ENTER
  or `L_xxxx:` in src/gen (relift to clean); event log id 1000 + `tools/faultline.sh
  <base+offset> build/ntexplorer_<mod>.dll`.

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
