# Survey: Windows XP against the Windows 2000 runtime

Source: Windows XP Media Center Edition 2005 SP3 (`VRMHOEM_EN.ISO`, I386),
NT 5.1 build 2600, file versions 5.1.2600.5512. No plain XP Pro/Home ISO
was available; MCE's I386 core (ntdll, kernel32, user32, gdi32, cmd, the
accessories) is XP Pro SP3's.

Numbers below were read off this ISO's own files (`tools/svctable.py`,
`tools/disas.py`), not from symbols.

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

The GDI difference is version-gated in pcrecomp (`nt_gdi_devcaps`). The WND
shift touches every offset in w32kuser.c / w32klayout.h from 0x30 on; that
is stage 3's work (still to do: SERVERINFO, DC_ATTR, the callback table
indexes and SHAREDINFO will need the same reading).

## 5. What applies from the Windows 2000 runtime as-is

- native32 module mapping, the dispatch, seh32, the launch guard, regbox32
  (boxed under `HKCU\Software\pcrecomp\xp\<app>`), the FILEBOX.
- syscall32.c's overrides by name; nt_boot's PEB/TEB (NT 5.0 offsets are
  NT 5.1's for every field it sets). The guest version comes from ntdll's
  VS_FIXEDFILEINFO: 5.1.2600.
- csr32.c's connect and console info.
- Not yet: w32kuser.c / w32klayout's USER layouts (section 4), activation
  contexts (comctl32 v6 by manifest: XP's loader asks csrss/sxs for the
  process default context; nothing answers yet), uxtheme.
