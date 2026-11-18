/*
 * nthost: Windows 2000's own cmd.exe on Windows 2000's own msvcrt, kernel32
 * and ntdll, all lifted, on the host's kernel. The guest's int 2Eh is the
 * only boundary (pcrecomp native32 syscall32.c, csrss in csr32.c). The host
 * maps the lifted modules; Windows 2000's own LdrInitializeThunk does the
 * rest of process start (native32_nt_boot). Stage 2 of docs/findings.md.
 *
 *   build\cmd.exe [--headless] [--mute] [--watchdog S] [--sys DIR] [--nls DIR] [-- cmd args]
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wctype.h>
#include <psapi.h>
#pragma comment(lib, "psapi.lib")

#include "native32.h"
#include "recomp_trace.h"
extern const char* g_cur_import;

#define ARG(n) MEM32(g_esp + 4 + 4 * (n))
#define NTDLL 0x20000000u
#ifndef W2K_EXE                /* the program: cmd.exe unless the build says otherwise */
#define W2K_EXE "cmd.exe"
#define W2K_EXE_W L"cmd.exe"
#define EXE_BASE 0x4AD00000u
#define W2K_MORE_MODS
#endif
#ifndef W2K_SYS               /* where this build's rebased modules and NLS files are */
#define W2K_SYS "work/rebased"
#define W2K_NLS "work/sys"
#define W2K_CSD 0x0400         /* Service Pack 4 */
#endif
static native32_module_t g_mods[] = {
    { W2K_EXE, EXE_BASE }, { "ntdll.dll", NTDLL }, { "kernel32.dll", 0x20100000u }, { "msvcrt.dll", 0x20200000u }
    W2K_MORE_MODS
};
#define NMODS ((int)(sizeof g_mods / sizeof g_mods[0]))
static DWORD g_watchdog_s;

void recomp_not_lifted(uint32_t va) {
    fprintf(stderr, "\n[not-lifted] sub_%08X  (called from 0x%08X)\n", va, g_cur_func);
    native32_dump_icalls(8);
    fflush(stderr);
    TerminateProcess(GetCurrentProcess(), 2);
}

recomp_func_t recomp_lookup_manual(uint32_t va) { (void)va; return NULL; }

static LONG CALLBACK crash(EXCEPTION_POINTERS* ep) {
    EXCEPTION_RECORD* r = ep->ExceptionRecord;
    HMODULE hm;
    if (getenv("W2K_ALL_FAULTS")) {     /* every host exception, first chance */
        fprintf(stderr, "[host] exception %08lX at %p (in sub_%08X, last native %s)\n", r->ExceptionCode,
                r->ExceptionAddress, g_cur_func, g_cur_import);
        fflush(stderr);
    }
    if ((r->ExceptionCode & 0xF0000000u) != 0xC0000000u) return EXCEPTION_CONTINUE_SEARCH;
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (LPCSTR)r->ExceptionAddress, &hm) && hm != GetModuleHandleA(NULL) && !getenv("W2K_ALL_FAULTS"))
        return EXCEPTION_CONTINUE_SEARCH;
    fprintf(stderr, "\n=== fault 0x%08lX at %p (access %08lX) ===\n  in lifted sub_%08X, last native call %s\n",
            r->ExceptionCode, r->ExceptionAddress, (unsigned long)(r->NumberParameters > 1 ? r->ExceptionInformation[1] : 0),
            g_cur_func, g_cur_import);
    {
        /* code outside every loaded module: name the mapping behind it */
        MEMORY_BASIC_INFORMATION mb;
        char f[MAX_PATH] = "";
        if (VirtualQuery(r->ExceptionAddress, &mb, sizeof mb))
            GetMappedFileNameA(GetCurrentProcess(), r->ExceptionAddress, f, MAX_PATH),
            fprintf(stderr, "  code in a %s mapping at %p: %s\n", mb.Type == MEM_IMAGE ? "image" : mb.Type == MEM_MAPPED ? "file" : "private",
                    mb.AllocationBase, f);
    }
    fprintf(stderr, "  eax=%08X ecx=%08X edx=%08X ebx=%08X esp=%08X ebp=%08X esi=%08X edi=%08X\n",
            g_eax, g_ecx, g_edx, g_ebx, g_esp, g_ebp, g_esi, g_edi);
    native32_dump_icalls(12);
    fprintf(stderr, "  pid %lu; guest stack code addresses:", GetCurrentProcessId());
    for (int i = 0, k = 0; i < 2048 && k < 40; i++)   /* the callers (return addresses, some stale) */
        if (!IsBadReadPtr((void*)(uintptr_t)(g_esp + 4 * i), 4) && native32_in_guest(MEM32(g_esp + 4 * i)))
            fprintf(stderr, " %08X", MEM32(g_esp + 4 * i)), k++;
    fprintf(stderr, "\n");
    recomp_dump_trace("fault");
    recomp_trace_flush();
    fflush(stderr);
    TerminateProcess(GetCurrentProcess(), 3);
    return EXCEPTION_CONTINUE_SEARCH;
}

static DWORD WINAPI watchdog(LPVOID unused) {
    (void)unused;
    if (getenv("W2K_PEEK")) {          /* W2K_PEEK=addr,addr,...: dwords at the watchdog */
        char buf[512], *t, *ctx = NULL;
        strncpy(buf, getenv("W2K_PEEK"), sizeof buf - 1);
        Sleep(g_watchdog_s * 1000 - 500);
        for (t = strtok_s(buf, ",", &ctx); t; t = strtok_s(NULL, ",", &ctx))
            fprintf(stderr, "[peek] %08X = %08X\n",(uint32_t)strtoul(t, NULL, 16), MEM32(strtoul(t, NULL, 16)));
    }
    Sleep(g_watchdog_s * 1000);
    fprintf(stderr, "\n[watchdog] %lu s: in sub_%08X, last native call %s\n", g_watchdog_s, g_cur_func, g_cur_import);
    if (native32_guest_peb && MEM32(native32_guest_peb + 0xA0)) {
        /* The guest's held critical sections: every one is on the list the
         * loader lock's DebugInfo (+0) is linked into (ProcessLocksList +8;
         * the section is DebugInfo +4; OwningThread +0xC, LockSemaphore +0x10) */
        uint32_t head = MEM32(MEM32(native32_guest_peb + 0xA0)) + 8, e = MEM32(head);
        for (int n = 0; e && e != head && n < 4096; e = MEM32(e), n++) {
            uint32_t cs = MEM32(e - 8 + 4);
            if (cs && !IsBadReadPtr((void*)(uintptr_t)cs, 0x18) && (MEM32(cs + 0xC) || MEM32(cs + 4) != 0xFFFFFFFFu))
                fprintf(stderr, "[watchdog] lock %08X held by t%lu (count %d, semaphore %X)\n", cs,
                        (unsigned long)MEM32(cs + 0xC), (int)MEM32(cs + 4), (int)MEM32(cs + 8), MEM32(cs + 0x10));
        }
    }
    fflush(stderr);
    native32_dump_icalls(8);
    recomp_dump_trace("watchdog");
    recomp_trace_flush();
    TerminateProcess(GetCurrentProcess(), 4);
    return 0;
}

/* The guest's ExitProcess ends in NtTerminateProcess: flush what the host
 * buffers (--calltrace, stdio) before the host kernel ends us. */
static uint32_t nt_terminate_process(uint32_t* a) {
    if (a[0] == 0xFFFFFFFFu || a[0] == 0 || GetProcessId((HANDLE)(uintptr_t)a[0]) == GetCurrentProcessId()) {
        if (a[1] >= 0xC0000000u) {      /* an exception's code: the guest's last-chance handler */
            fprintf(stderr, "\n[nt] the guest ends itself with %08X\n", a[1]);
            native32_dump_icalls(12);
            recomp_dump_trace("terminate");
        }
        recomp_trace_flush();
        fflush(NULL);
    }
    return native32_nt_forward("NtTerminateProcess", a);
}
/* ---- stage 3 probe: win32k ----------------------------------------------
 * ponytail: the first services a lifted gdi32/user32 needs, answered just
 * enough to see the next one. Not an implementation of win32k. */
static uint32_t w32k_gdi_init(uint32_t* a) {
    (void)a;
    /* GdiSharedHandleTable: 16384 Win2000 GDI_TABLE_ENTRYs (16 bytes) */
    if (!MEM32(native32_guest_peb + 0x94))
        MEM32(native32_guest_peb + 0x94) = (uint32_t)(uintptr_t)VirtualAlloc(NULL, 0x80000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);   /* + the shared data after it (gdi32 reads +0x40094) */
    return 1;
}
/* W2K_FIXED_TIME=seconds: the lifted msvcrt's time() answers that (a lifted
 * function in the guest model: argument on the stack, result in eax). */
static void fixed_time(void) {
    uint32_t v = strtoul(getenv("W2K_FIXED_TIME"), NULL, 0), p = MEM32(g_esp + 4);
    if (p) MEM32(p) = v;
    g_eax = v;
    g_esp += 4;
}

/* W2K_FIXED_TICK=n: the lifted kernel32's GetTickCount answers n (it reads
 * KUSER_SHARED_DATA, no system call to catch) */
static void fixed_tick(void) {
    g_eax = strtoul(getenv("W2K_FIXED_TICK"), NULL, 0);
    g_esp += 4;
}

/* A guest stdcall export answered by the registry sandbox's function of that
 * name (pcrecomp regbox32.c), n arguments. */
static void sandbox_call(const char* name, int n) {
    uint32_t* a = (uint32_t*)(uintptr_t)(g_esp + 4);
    void* f = native32_registry_sandbox_fn(name);
    typedef uint32_t (WINAPI *f2)(uint32_t, uint32_t);
    typedef uint32_t (WINAPI *f3)(uint32_t, uint32_t, uint32_t);
    typedef uint32_t (WINAPI *f4)(uint32_t, uint32_t, uint32_t, uint32_t);
    typedef uint32_t (WINAPI *f5)(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);
    typedef uint32_t (WINAPI *f6)(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);
    g_eax = !f ? 0 : n == 2 ? ((f2)f)(a[0], a[1]) : n == 3 ? ((f3)f)(a[0], a[1], a[2])
          : n == 4 ? ((f4)f)(a[0], a[1], a[2], a[3]) : n == 5 ? ((f5)f)(a[0], a[1], a[2], a[3], a[4])
          : ((f6)f)(a[0], a[1], a[2], a[3], a[4], a[5]);
    g_esp += 4 + 4 * n;
}
#define PS(name, n) static void ps_##name(void) { sandbox_call(#name, n); }
PS(WriteProfileStringW, 3) PS(WriteProfileStringA, 3) PS(WritePrivateProfileStringW, 4) PS(WritePrivateProfileStringA, 4)
PS(GetProfileStringW, 5) PS(GetPrivateProfileStringW, 6) PS(GetProfileIntW, 3) PS(GetPrivateProfileIntW, 4)
PS(WriteProfileSectionW, 2) PS(WriteProfileSectionA, 2) PS(WritePrivateProfileSectionW, 3) PS(WritePrivateProfileSectionA, 3)
PS(WritePrivateProfileStructW, 5) PS(WritePrivateProfileStructA, 5)

#if defined(W2K_USER_LAYER)
/* The guest's AdjustWindowRectEx(RECT*, style, bMenu, exstyle) answered by
 * the host's: a window sized from its client area afterwards (sol) gets the
 * host's frame, which is the frame it is drawn with. */
static void host_adjust(void) {
    g_eax = AdjustWindowRectEx((RECT*)(uintptr_t)ARG(0), ARG(1), ARG(2), ARG(3));
    g_esp += 4 + 16;
}
/* The guest's DrawTextW(hdc, text, count, RECT*, format) answered by the
 * host's: Windows 11's DrawText draws OPAQUE text differently from Windows
 * 2000's (which ExtTextOutW's it), ClearType pixels a level apart on calc's
 * buttons; a stage 1 program gets the host's. */
static void host_drawtext(void) {
    HDC h = (HDC)native32_gdi_dc(ARG(0));
    g_eax = (uint32_t)DrawTextW(h, (LPCWSTR)(uintptr_t)ARG(1), (int)ARG(2), (RECT*)(uintptr_t)ARG(3), ARG(4));
    g_esp += 4 + 20;
}
/* DrawTextA too (packager): the host's DT_CALCRECT is a pixel narrower than
 * Windows 2000's for the same font, and packager sizes its labels with it */
static void host_drawtexta(void) {
    HDC h = (HDC)native32_gdi_dc(ARG(0));
    g_eax = (uint32_t)DrawTextA(h, (LPCSTR)(uintptr_t)ARG(1), (int)ARG(2), (RECT*)(uintptr_t)ARG(3), ARG(4));
    g_esp += 4 + 20;
}
/* CallNextHookEx(hhk, code, wParam, lParam): Windows 2000's walks the
 * thread's hook chain client-side (CLIENTINFO); the hooks are the host's */
/* MsgWaitForMultipleObjects(Ex): Windows 2000's asks win32k for the queue's
 * input event (NtUserCallOneParam 0x1D, GetInputEvent) and waits on it with
 * the caller's handles; the host queue has no such event to hand out, the
 * call failed at once and explorer's tray loop spun. The guest's handles are
 * the host's, so the host's own wait, with the machine given up. */
static void host_msgwait(int ex) {
    DWORD n = ARG(0), r;
    HANDLE* h = (HANDLE*)(uintptr_t)ARG(1);
    int held = mach_release();
    r = ex ? MsgWaitForMultipleObjectsEx(n, h, ARG(2), ARG(3), ARG(4))
           : MsgWaitForMultipleObjects(n, h, (BOOL)ARG(2), ARG(3), ARG(4));
    mach_reacquire(held);
    g_eax = r;
    g_esp += 4 + 20;
}
static void host_msgwait_ex(void) { host_msgwait(1); }
static void host_msgwait_all(void) { host_msgwait(0); }
static void host_nexthook(void) {
    g_eax = (uint32_t)CallNextHookEx(NULL, (int)ARG(1), ARG(2), ARG(3));
    g_esp += 4 + 16;
}
/* GetProp(hwnd, name): Windows 2000's reads the WND's property list
 * client-side; the properties are the host window's (NtUserSetProp) */
static void host_getpropw(void) { g_eax = (uint32_t)(uintptr_t)GetPropW((HWND)(uintptr_t)ARG(0), (LPCWSTR)(uintptr_t)ARG(1)); g_esp += 4 + 8; }
static void host_getpropa(void) { g_eax = (uint32_t)(uintptr_t)GetPropA((HWND)(uintptr_t)ARG(0), (LPCSTR)(uintptr_t)ARG(1)); g_esp += 4 + 8; }
static void host_getscrollinfo(void) { g_eax = GetScrollInfo((HWND)(uintptr_t)ARG(0), (int)ARG(1), (SCROLLINFO*)(uintptr_t)ARG(2)); g_esp += 4 + 12; }
static void host_getscrollpos(void) { g_eax = (uint32_t)GetScrollPos((HWND)(uintptr_t)ARG(0), (int)ARG(1)); g_esp += 4 + 8; }
static void host_getscrollrange(void) { g_eax = GetScrollRange((HWND)(uintptr_t)ARG(0), (int)ARG(1), (int*)(uintptr_t)ARG(2), (int*)(uintptr_t)ARG(3)); g_esp += 4 + 16; }
/* CallWindowProc(proc, hwnd, msg, wParam, lParam) to a HOST procedure (a
 * comctl32 control MFC subclassed): GDI handles in the message are the
 * guest's, so they go over as the host's. MFC's CToolBar adds its image
 * well with TB_ADDBITMAP / TB_REPLACEBITMAP through it (wordpad, mspaint).
 * A guest procedure gets the message as it is. Then Windows 2000's own. */
static recomp_func_t g_cwp_w, g_cwp_a;
static void cwp_host(void) {
    static uint32_t tb[5];
    uint32_t proc = ARG(0), m = ARG(2), l = ARG(4);
    if (proc < 0x10000 || native32_in_guest(proc)) return;
    if (ARG(3) && native32_gdi_host(ARG(3))) MEM32(g_esp + 16) = native32_gdi_host(ARG(3));
    if ((m == 0x413 || m == 0x42E) && l) {           /* TB_ADDBITMAP, TB_REPLACEBITMAP */
        memcpy(tb, (void*)(uintptr_t)l, m == 0x413 ? 8 : 20);
        if (!tb[0] && native32_gdi_host(tb[1])) tb[1] = native32_gdi_host(tb[1]);
        if (m == 0x42E && !tb[2] && native32_gdi_host(tb[3])) tb[3] = native32_gdi_host(tb[3]);
        MEM32(g_esp + 20) = (uint32_t)(uintptr_t)tb;
    }
}
static void host_cwp_w(void) { cwp_host(); g_cwp_w(); }
static void host_cwp_a(void) { cwp_host(); g_cwp_a(); }
/* CreateDCW(driver, device, port, DEVMODEW*): MFC's printer DC (wordpad wraps
 * to the printer). Windows 2000's gdi32 resolves a printer through its own
 * spooler and opened a device of NULL (the display) here; the host's. */
static void host_createdcw(void) {
    HDC h = CreateDCW((LPCWSTR)(uintptr_t)ARG(0), (LPCWSTR)(uintptr_t)ARG(1), (LPCWSTR)(uintptr_t)ARG(2), (DEVMODEW*)(uintptr_t)ARG(3));
    g_eax = native32_gdi_handle((uint32_t)(uintptr_t)h);
    g_esp += 4 + 16;
}
static void host_adjust3(void) {
    g_eax = AdjustWindowRect((RECT*)(uintptr_t)ARG(0), ARG(1), ARG(2));
    g_esp += 4 + 12;
}
#endif
/* CreateProcessW/A(app, cmdline, psa, tsa, inherit, flags, env, dir, si, pi):
 * the guard's launch path. The program named must be a lifted one with a
 * host runner next to this one (build\nt<name>.exe, else build\<name>.exe:
 * cmd, find, more), built from its lift; that runner is started as a new
 * host process with the guest's arguments, inherit flag, creation flags and
 * standard handles (cmd's pipes; guest handles are host handles), on the
 * same virtual screen (W2K_SCREEN_HWND is in our environment).
 * Anything else, an original or a host program included, is refused. */
static void host_createprocess(int ansi) {
    wchar_t buf[1024], run[MAX_PATH], line[1400], stem[64];
    const wchar_t* p, *args = L"";
    size_t n = 0;
    uint32_t app = ARG(0), cl = ARG(1), pi = ARG(9);
    STARTUPINFOW si = { sizeof si };
    PROCESS_INFORMATION out;
    buf[0] = 0;
    if (app || cl) {
        if (ansi) MultiByteToWideChar(CP_ACP, 0, (const char*)(uintptr_t)(app ? app : cl), -1, buf, 1023);
        else wcsncpy(buf, (const wchar_t*)(uintptr_t)(app ? app : cl), 1023);
        buf[1023] = 0;
    }
    if (cl) {   /* the arguments: the command line after its first token */
        static wchar_t cw[1024];
        const wchar_t* c = cw;
        if (ansi) MultiByteToWideChar(CP_ACP, 0, (const char*)(uintptr_t)cl, -1, cw, 1023);
        else wcsncpy(cw, (const wchar_t*)(uintptr_t)cl, 1023);
        cw[1023] = 0;
        while (*c == L' ') c++;
        if (*c == L'"') { c = wcschr(c + 1, L'"'); c = c ? c + 1 : L""; }
        else while (*c && *c != L' ') c++;
        args = c;
    }
    /* the image's file name (no directory, no quotes), its stem */
    p = buf;
    while (*p == L' ' || *p == L'"') p++;
    {
        const wchar_t* end = p;
        while (*end && *end != L'"' && (app || *end != L' ')) end++;
        for (const wchar_t* q = p; q < end; q++) if (*q == L'\\' || *q == L'/' || *q == L':') p = q + 1;
        while (p + n < end && n < 63) stem[n] = towlower(p[n]), n++;
        stem[n] = 0;
    }
    if (n > 4 && (!wcscmp(stem + n - 4, L".exe") || !wcscmp(stem + n - 4, L".com"))) stem[n -= 4] = 0;
    for (size_t i = 0; i < n; i++) if (!iswalnum(stem[i]) && stem[i] != L'_') n = 0;
    GetModuleFileNameW(NULL, run, MAX_PATH);
    if (wcsrchr(run, L'\\')) wcsrchr(run, L'\\')[1] = 0;
    wcsncat(run, L"nt", MAX_PATH - wcslen(run) - 1);
    wcsncat(run, stem, MAX_PATH - wcslen(run) - 5);
    wcscat(run, L".exe");
    /* the runner named itself (the box's App Paths point there: "winmine" in the Run dialog) */
    if (n > 2 && !wcsncmp(stem, L"nt", 2) && GetFileAttributesW(run) == INVALID_FILE_ATTRIBUTES) {
        wchar_t* s = wcsrchr(run, L'\\') + 1;
        memmove(s + 2, s + 4, (wcslen(s + 4) + 1) * sizeof *s);
    }
    if (n && GetFileAttributesW(run) == INVALID_FILE_ATTRIBUTES) {   /* build\<name>.exe: cmd, find, more */
        wchar_t* s = wcsrchr(run, L'\\') + 1;
        if (!wcsncmp(s, L"nt", 2)) memmove(s, s + 2, (wcslen(s + 2) + 1) * sizeof *s);
    }
    if (!n || GetFileAttributesW(run) == INVALID_FILE_ATTRIBUTES) {
        fprintf(stderr, "[guard] CreateProcess %ls: not a lifted program: refused\n", buf);
        SetLastError(ERROR_ACCESS_DENIED);
        g_eax = 0;
        g_esp += 4 + 40;
        return;
    }
    _snwprintf(line, 1399, L"\"%ls\" --mute --raw%ls", run, args);
    line[1399] = 0;
    if (ARG(8)) {   /* STARTUPINFO: A and W share the layout of these fields */
        const STARTUPINFOW* g = (const STARTUPINFOW*)(uintptr_t)ARG(8);
        si.dwFlags = g->dwFlags & (STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW);
        si.wShowWindow = g->wShowWindow;
        si.hStdInput = g->hStdInput, si.hStdOutput = g->hStdOutput, si.hStdError = g->hStdError;
    }
    {   /* The guest's environment block (its own, or the one it passed) and current
         * directory reach the child's GUEST only: PCRECOMP_GUEST_ENV (entries split
         * by U+0001) and PCRECOMP_GUEST_CWD, read by the child's process parameters
         * (pcrecomp syscall32.c). The child runner's host environment stays ours, so
         * a guest `set PCRECOMP_FILEBOX=` or Path never reaches a host loader. */
        static wchar_t ge[32760], gc[MAX_PATH];
        const uint8_t* pp = (const uint8_t*)(uintptr_t)*(uint32_t*)(uintptr_t)(native32_guest_peb + 0x10);
        uintptr_t env = ARG(6) ? ARG(6) : *(uint32_t*)(pp + 0x48);
        int wide = !ARG(6) || (ARG(5) & CREATE_UNICODE_ENVIRONMENT);
        size_t o = 0;
        while (env) {
            wchar_t v[4096];
            size_t k = wide ? wcslen((const wchar_t*)env) : strlen((const char*)env);
            if (!k) break;
            if (wide) wcsncpy(v, (const wchar_t*)env, 4095);
            else MultiByteToWideChar(CP_ACP, 0, (const char*)env, -1, v, 4095);
            v[4095] = 0;
            env += (k + 1) * (wide ? 2 : 1);
            if (o + wcslen(v) + 2 >= sizeof ge / 2) break;   /* ponytail: the rest of a huge block dropped */
            if (o) ge[o++] = 1;
            wcscpy(ge + o, v), o += wcslen(v);
        }
        ge[o] = 0;
        gc[0] = 0;
        if (ARG(7)) {
            if (ansi) MultiByteToWideChar(CP_ACP, 0, (const char*)(uintptr_t)ARG(7), -1, gc, MAX_PATH - 1);
            else wcsncpy(gc, (const wchar_t*)(uintptr_t)ARG(7), MAX_PATH - 1);
        } else if (*(uint16_t*)(pp + 0x24) / 2 < MAX_PATH) {
            memcpy(gc, (const void*)(uintptr_t)*(uint32_t*)(pp + 0x28), *(uint16_t*)(pp + 0x24));
            gc[*(uint16_t*)(pp + 0x24) / 2] = 0;
        }
        gc[MAX_PATH - 1] = 0;
        SetEnvironmentVariableW(L"PCRECOMP_GUEST_ENV", o ? ge : NULL);
        SetEnvironmentVariableW(L"PCRECOMP_GUEST_CWD", gc[0] ? gc : NULL);
    }
    if (!CreateProcessW(run, line, NULL, NULL, ARG(4) != 0,
                        ARG(5) & CREATE_SUSPENDED,   /* ponytail: no new console or detach: the runner logs to our stderr */
                        NULL, NULL, &si, &out)) {
        g_eax = 0;
    } else {
        fprintf(stderr, "[launch] %ls -> %ls (pid %lu, flags %08X, si %08lX): %ls\n", stem, run, out.dwProcessId, ARG(5), si.dwFlags, line);
        if (pi) memcpy((void*)(uintptr_t)pi, &out, sizeof out);
        else CloseHandle(out.hProcess), CloseHandle(out.hThread);
        g_eax = 1;
    }
    g_esp += 4 + 40;
}
static void host_createprocessw(void) { host_createprocess(0); }
static void host_createprocessa(void) { host_createprocess(1); }

static int host_main(int argc, char** argv) {
    const char* sys = W2K_SYS, *nlsdir = W2K_NLS;
    char dir[MAX_PATH], nls[MAX_PATH];
    wchar_t cmdline[1024] = W2K_EXE_W, image[MAX_PATH];
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--mute") || !strcmp(argv[i], "--headless")) SetEnvironmentVariableA("PCRECOMP_MUTE", "1");
    for (int i = 1; i < argc; i++) {
        int rc;
        if (!strcmp(argv[i], "--headless") && (rc = native32_headless()) >= 0) return rc;
    }
    for (int i = 1; i < argc; i++) {
        int n = recomp_trace_arg(argc, argv, i);
        if (n) { i += n - 1; continue; }
        if (!strcmp(argv[i], "--headless") || !strcmp(argv[i], "--mute")) ;
        else if (!strcmp(argv[i], "--watchdog") && i + 1 < argc) g_watchdog_s = strtoul(argv[++i], NULL, 0);
        else if (!strcmp(argv[i], "--native-trace")) native32_trace_native = 1;
        else if (!strcmp(argv[i], "--sys") && i + 1 < argc) sys = argv[++i];
        else if (!strcmp(argv[i], "--nls") && i + 1 < argc) nlsdir = argv[++i];
        else if (!strcmp(argv[i], "--raw")) {
            /* the launch path's: the rest of our command line as it is, quotes kept (find "hi") */
            const wchar_t* r = wcsstr(GetCommandLineW(), L" --raw");
            if (r) _snwprintf(cmdline + wcslen(cmdline), 1023 - wcslen(cmdline), L"%ls", r + 6);
            break;
        }
        else if (!strcmp(argv[i], "--")) {
            while (++i < argc) {
                size_t n = wcslen(cmdline);
                _snwprintf(cmdline + n, 1023 - n, L" %hs", argv[i]);
            }
            break;
        }
        else { printf("usage: cmd [--headless] [--mute] [--watchdog S] [--native-trace] [-- args]\n"); return 1; }
    }
    GetFullPathNameA(sys, MAX_PATH, dir, NULL);
    GetFullPathNameA(nlsdir, MAX_PATH, nls, NULL);
    {
        char exe[MAX_PATH];
        _snprintf(exe, sizeof exe - 1, "%s\\%s", dir, W2K_EXE);
        exe[MAX_PATH - 1] = 0;
        native32_hold_image(exe, EXE_BASE);
        MultiByteToWideChar(CP_ACP, 0, exe, -1, image, MAX_PATH);
    }
    {   /* the guest never writes the user's registry: HKCU\Software\pcrecomp\w2k\<app> (pcrecomp regbox32.c) */
        char box[64] = "xp\\";
        strncat(box, W2K_EXE, 40);
        *strrchr(box, '.') = 0;
        /* a program a guest launched shares its launcher's box (one HKCU, as on Windows
         * 2000: winmine on explorer's screen takes the box's Control Panel\Colors) */
        if (getenv("W2K_REGBOX")) strncpy(box, getenv("W2K_REGBOX"), 63), box[63] = 0;
        SetEnvironmentVariableA("W2K_REGBOX", box);
        if (!native32_registry_sandbox(box)) { fprintf(stderr, "no registry sandbox: not running\n"); return 1; }
        native32_registry_sandbox_nt(native32_nt_override, native32_nt_forward, native32_nt_proxy_hook);
    }
    {   /* XP's side-by-side store (pcrecomp csr32.c): <sys>\sxs\<assembly>\ */
        char sxs[MAX_PATH];
        _snprintf(sxs, MAX_PATH - 1, "%s\\sxs", dir);
        sxs[MAX_PATH - 1] = 0;
        SetEnvironmentVariableA("PCRECOMP_SXS", sxs);
    }
    native32_init();
    AddVectoredExceptionHandler(0, crash);
    /* Mapped, not bound: the guest's own loader snaps every import. */
    if (!native32_modules_map(dir, dir, g_mods, NMODS)) return 1;
    native32_nt_override("NtTerminateProcess", nt_terminate_process);
    native32_nt_syscalls(NTDLL);
    {
        /* user32 and gdi32 lifted too: their win32k services */
        uint32_t w[2], n = 0;
        if ((w[n] = native32_module("user32.dll")) != 0) n++;
        if ((w[n] = native32_module("gdi32.dll")) != 0) n++;
        if (n) native32_nt_win32k(w, (int)n, "work/names/win32k.txt");
#if defined(W2K_USER_LAYER)
        if (n) native32_gdi_install(), native32_user_install();   /* win32k: w32kgdi.c + w32kuser.c */
#elif defined(W2K_GDI_LAYER)
        if (n) native32_gdi_install();      /* GDI on the host's GDI (pcrecomp w32kgdi.c) */
#else
        if (n) native32_nt_win32k_override("NtGdiInit", w32k_gdi_init);
#endif
    }
    {
        /* csrss's \NLS sections, from Windows 2000's own NLS files */
        static const struct { const wchar_t* sec; const char* file; } nls_sec[] = {
            { L"\\NLS\\NlsSectionUnicode", "unicode.nls" }, { L"\\NLS\\NlsSectionCType", "ctype.nls" },
            { L"\\NLS\\NlsSectionLocale", "locale.nls" }, { L"\\NLS\\NlsSectionSortkey", "sortkey.nls" },
            { L"\\NLS\\NlsSectionSortTbls", "sorttbls.nls" }, { L"\\NLS\\NlsSectionCP1252", "c_1252.nls" },
            { L"\\NLS\\NlsSectionCP437", "c_437.nls" }, { L"\\NLS\\NlsSectionLANG_INTL", "l_intl.nls" },
            { L"\\NLS\\NlsSectionSortkey00000409", "sortkey_00000409.nls" },
        };
        /* csrss's per-locale sort table: sortkey.nls whole, its first WORD set
         * to 1 ("built"; kernel32 waits while it is 0). US English has no
         * exceptions to apply. Written once next to the NLS files. */
        char src[MAX_PATH], dst[MAX_PATH];
        _snprintf(src, MAX_PATH - 1, "%s\\sortkey.nls", nls);
        _snprintf(dst, MAX_PATH - 1, "%s\\sortkey_00000409.nls", nls);
        if (GetFileAttributesA(dst) == INVALID_FILE_ATTRIBUTES && CopyFileA(src, dst, TRUE)) {
            FILE* f = fopen(dst, "r+b");
            if (f) { uint16_t one = 1; fwrite(&one, 2, 1, f); fclose(f); }
        }
        for (int i = 0; i < (int)(sizeof nls_sec / sizeof nls_sec[0]); i++) {
            wchar_t f[MAX_PATH];
            _snwprintf(f, MAX_PATH - 1, L"%hs\\%hs", nls, nls_sec[i].file);
            f[MAX_PATH - 1] = 0;
            native32_nt_section_file(nls_sec[i].sec, f);
        }
    }
    if (g_watchdog_s) CloseHandle(CreateThread(NULL, 0, watchdog, NULL, 0, NULL));
    {
        /* The loader's search path: the lifted modules first, then the host's
         * system directory (host DLLs, as proxies). */
        wchar_t dllpath[2 * MAX_PATH], sysw[MAX_PATH];
        GetSystemDirectoryW(sysw, MAX_PATH);
        _snwprintf(dllpath, 2 * MAX_PATH - 1, L"%hs;%ls", dir, sysw);
        dllpath[2 * MAX_PATH - 1] = 0;
        if (!native32_nt_boot(NTDLL, EXE_BASE, image, cmdline, dllpath, nls, W2K_CSD)) return 1;
    }
#ifdef W2K_GDI_LAYER
    if (!native32_gdi_start(native32_module("gdi32.dll"))) fprintf(stderr, "gdi32 has no GdiDllInitialize\n");
#endif
#if defined(W2K_USER_LAYER)
    {
        /* (replaced by address: only a program's calls through its IAT see
         * it; user32's own direct calls keep Windows 2000's) */
        uint32_t u = native32_module("user32.dll");
        native32_replace(native32_export(u, "AdjustWindowRectEx"), host_adjust);
        native32_replace(native32_export(u, "AdjustWindowRect"), host_adjust3);
        native32_replace(native32_export(u, "DrawTextW"), host_drawtext);
        native32_replace(native32_export(u, "DrawTextA"), host_drawtexta);
        native32_replace(native32_export(u, "CallNextHookEx"), host_nexthook);
        native32_replace(native32_export(u, "MsgWaitForMultipleObjectsEx"), host_msgwait_ex);
        native32_replace(native32_export(u, "MsgWaitForMultipleObjects"), host_msgwait_all);
        native32_replace(native32_export(u, "GetPropW"), host_getpropw);
        native32_replace(native32_export(u, "GetPropA"), host_getpropa);
        native32_replace(native32_export(u, "GetScrollInfo"), host_getscrollinfo);
        native32_replace(native32_export(u, "GetScrollPos"), host_getscrollpos);
        native32_replace(native32_export(u, "GetScrollRange"), host_getscrollrange);
        g_cwp_w = recomp_lookup(native32_export(u, "CallWindowProcW"));
        g_cwp_a = recomp_lookup(native32_export(u, "CallWindowProcA"));
        native32_replace(native32_export(native32_module("gdi32.dll"), "CreateDCW"), host_createdcw);
        if (g_cwp_w) native32_replace(native32_export(u, "CallWindowProcW"), host_cwp_w);
        if (g_cwp_a) native32_replace(native32_export(u, "CallWindowProcA"), host_cwp_a);
    }
#endif
    native32_mute_winmm();   /* --mute: winmm reports no devices, refuses every open */
    {   /* the launch path: lifted programs only, each in its own host runner (cmd's pipes too) */
        uint32_t k = native32_module("kernel32.dll");
        native32_replace(native32_export(k, "CreateProcessW"), host_createprocessw);
        native32_replace(native32_export(k, "CreateProcessA"), host_createprocessa);
    }
    {   /* the lifted kernel32's profile calls (win.ini): the registry sandbox's */
        static const struct { const char* name; recomp_func_t fn; } prof[] = {
            { "WriteProfileStringW", ps_WriteProfileStringW }, { "WriteProfileStringA", ps_WriteProfileStringA },
            { "WritePrivateProfileStringW", ps_WritePrivateProfileStringW },
            { "WritePrivateProfileStringA", ps_WritePrivateProfileStringA },
            { "GetProfileStringW", ps_GetProfileStringW }, { "GetPrivateProfileStringW", ps_GetPrivateProfileStringW },
            { "GetProfileIntW", ps_GetProfileIntW }, { "GetPrivateProfileIntW", ps_GetPrivateProfileIntW },
            { "WriteProfileSectionW", ps_WriteProfileSectionW }, { "WriteProfileSectionA", ps_WriteProfileSectionA },
            { "WritePrivateProfileSectionW", ps_WritePrivateProfileSectionW },
            { "WritePrivateProfileSectionA", ps_WritePrivateProfileSectionA },
            { "WritePrivateProfileStructW", ps_WritePrivateProfileStructW },
            { "WritePrivateProfileStructA", ps_WritePrivateProfileStructA },
        };
        uint32_t k32 = native32_module("kernel32.dll");
        for (int i = 0; i < (int)(sizeof prof / sizeof prof[0]); i++) {
            uint32_t va = native32_export(k32, prof[i].name);
            if (va) native32_replace(va, prof[i].fn);
        }
    }
    if (getenv("W2K_FIXED_TICK"))
        native32_replace(native32_export(native32_module("kernel32.dll"), "GetTickCount"), fixed_tick);
    if (getenv("W2K_FIXED_TIME") && native32_module("msvcrt.dll"))
        native32_replace(native32_export(native32_module("msvcrt.dll"), "time"), fixed_time);
    if (getenv("W2K_IAT_DUMP")) {          /* imports the guest's loader left unsnapped */
        IMAGE_NT_HEADERS32* h = (IMAGE_NT_HEADERS32*)(uintptr_t)(EXE_BASE + MEM32(EXE_BASE + 0x3C));
        IMAGE_IMPORT_DESCRIPTOR* d = (IMAGE_IMPORT_DESCRIPTOR*)(uintptr_t)(EXE_BASE +
            h->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
        for (; d->Name; d++) {
            uint32_t* iat = (uint32_t*)(uintptr_t)(EXE_BASE + d->FirstThunk);
            uint32_t* ilt = (uint32_t*)(uintptr_t)(EXE_BASE + (d->OriginalFirstThunk ? d->OriginalFirstThunk : d->FirstThunk));
            for (; *ilt; ilt++, iat++)
                if (*iat < 0x10000)
                    fprintf(stderr, "[iat] %s!%s = %08X\n",(char*)(uintptr_t)(EXE_BASE + d->Name),
                            *ilt & 0x80000000u ? "#ord" : (char*)(uintptr_t)(EXE_BASE + *ilt + 2), *iat);
        }
    }
    IMAGE_NT_HEADERS32* nt = (IMAGE_NT_HEADERS32*)(uintptr_t)(EXE_BASE + MEM32(EXE_BASE + 0x3C));
    uint32_t entry = EXE_BASE + nt->OptionalHeader.AddressOfEntryPoint;
    fprintf(stderr, "%s: %u lifted functions, entering 0x%08X\n", W2K_EXE, recomp_dispatch_count, entry);
    native32_call_guest(entry, 0, NULL);
    if (g_eax >= 0xC0000000u) {     /* the entry point returned an exception's code */
        fprintf(stderr, "[nt] %s's entry returned %08X\n", W2K_EXE, g_eax);
        native32_dump_icalls(12);
        recomp_dump_trace("return");
    }
    return (int)g_eax;
}

static int g_argc;
static char** g_argv;
static DWORD WINAPI host_thread(LPVOID unused) { (void)unused; return (DWORD)host_main(g_argc, g_argv); }

int main(int argc, char** argv) {
    DWORD code = 1;
    g_argc = argc;
    g_argv = argv;
    HANDLE t = CreateThread(NULL, 16u << 20, host_thread, NULL, STACK_SIZE_PARAM_IS_A_RESERVATION, NULL);
    if (!t) return 1;
    WaitForSingleObject(t, INFINITE);
    GetExitCodeThread(t, &code);
    return (int)code;
}
