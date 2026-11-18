/*
 * apphost: one Windows 2000 accessory (winmine, sol, freecell, notepad,
 * calc), lifted whole and run on pcrecomp's native32 against the HOST's
 * Windows DLLs. Stage 1 of docs/findings.md. APP_EXE names the file in
 * work/sys; the lift of it is compiled in (src/gen/<app>).
 *
 *   build\winmine.exe --headless --mute [--sys DIR] [--watchdog S] [-- args]
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "native32.h"
extern const char* g_cur_import;

#ifndef APP_DLLS
#define APP_DLLS
#endif
static native32_module_t g_mods[] = { { APP_EXE, APP_BASE } APP_DLLS };
#define NMODS ((int)(sizeof g_mods / sizeof g_mods[0]))
static DWORD g_watchdog_s;

static char g_cmd_a[1024];   /* the guest's command line: its name + what follows "--" */

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
    if ((r->ExceptionCode & 0xF0000000u) != 0xC0000000u) return EXCEPTION_CONTINUE_SEARCH;
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (LPCSTR)r->ExceptionAddress, &hm) && hm != GetModuleHandleA(NULL))
        return EXCEPTION_CONTINUE_SEARCH;
    fprintf(stderr, "\n=== fault 0x%08lX at %p ===\n  in lifted sub_%08X, last native call %s\n",
            r->ExceptionCode, r->ExceptionAddress, g_cur_func, g_cur_import);
    fprintf(stderr, "  eax=%08X ecx=%08X edx=%08X ebx=%08X esp=%08X ebp=%08X esi=%08X edi=%08X\n",
            g_eax, g_ecx, g_edx, g_ebx, g_esp, g_ebp, g_esi, g_edi);
    native32_dump_icalls(12);
    fflush(stderr);
    TerminateProcess(GetCurrentProcess(), 3);
    return EXCEPTION_CONTINUE_SEARCH;
}

static DWORD WINAPI watchdog(LPVOID unused) {
    (void)unused;
    Sleep(g_watchdog_s * 1000);
    fprintf(stderr, "\n[watchdog] %lu s: in sub_%08X, last native call %s\n", g_watchdog_s, g_cur_func, g_cur_import);
    fflush(stderr);
    TerminateProcess(GetCurrentProcess(), 4);
    return 0;
}

/* W2K_FIXED_TIME=seconds: msvcrt's time() answers that, for runs that must
 * repeat (Solitaire seeds its deal with it). */
static unsigned __cdecl fixed_time(unsigned* t) {
    unsigned v = (unsigned)strtoul(getenv("W2K_FIXED_TIME"), NULL, 0);
    if (t) *t = v;
    return v;
}

/* W2K_FIXED_TICK=n: GetTickCount answers n (winmine seeds its mines with it) */
static DWORD WINAPI fixed_tick(void) { return (DWORD)strtoul(getenv("W2K_FIXED_TICK"), NULL, 0); }

static int host_main(int argc, char** argv) {
#ifndef APP_SYS
#define APP_SYS "work\\sys"
#endif
    const char* sys = APP_SYS;
    char dir[MAX_PATH];
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--mute") || !strcmp(argv[i], "--headless")) SetEnvironmentVariableA("PCRECOMP_MUTE", "1");
    for (int i = 1; i < argc; i++) {
        int rc;
        if (!strcmp(argv[i], "--headless") && (rc = native32_headless()) >= 0) return rc;
    }
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--headless") || !strcmp(argv[i], "--mute")) ;
        else if (!strcmp(argv[i], "--sys") && i + 1 < argc) sys = argv[++i];
        else if (!strcmp(argv[i], "--watchdog") && i + 1 < argc) g_watchdog_s = strtoul(argv[++i], NULL, 0);
        else if (!strcmp(argv[i], "--native-trace")) native32_trace_native = 1;
        else if (!strcmp(argv[i], "--")) {
            while (++i < argc) { strncat(g_cmd_a, " ", 1000 - strlen(g_cmd_a)); strncat(g_cmd_a, argv[i], 1000 - strlen(g_cmd_a)); }
            break;
        }
        else { printf("usage: %s [--headless] [--mute] [--sys DIR] [--watchdog S] [--native-trace]\n", APP_EXE); return 1; }
    }
    GetFullPathNameA(sys, MAX_PATH, dir, NULL);
    {
        char exe[MAX_PATH];
        _snprintf(exe, sizeof exe - 1, "%s\\%s", dir, APP_EXE);
        exe[MAX_PATH - 1] = 0;
        native32_hold_image(exe, APP_BASE);
    }
    {
        char tail[1024];
        strcpy(tail, g_cmd_a);
        _snprintf(g_cmd_a, sizeof g_cmd_a - 1, "%s%s", APP_EXE, tail);
        native32_set_command_line(g_cmd_a);
    }
    if (getenv("W2K_FIXED_TIME")) native32_redirect("time", (void*)fixed_time);
    if (getenv("W2K_FIXED_TICK")) native32_redirect("GetTickCount", (void*)fixed_tick);   /* a repeatable deal (tools/gdicmp.py) */
    {   /* the guest never writes the user's registry: HKCU\Software\pcrecomp\w2k\<app> (pcrecomp regbox32.c) */
        char box[64] = "xp\\";
        strncat(box, APP_EXE, 40);
        *strrchr(box, '.') = 0;
        if (!native32_registry_sandbox(box)) { fprintf(stderr, "no registry sandbox: not running\n"); return 1; }
    }
    native32_init();
    AddVectoredExceptionHandler(0, crash);
    if (!native32_modules_map(dir, dir, g_mods, NMODS)) return 1;
    int missing = native32_modules_bind(NULL, 0);
    if (missing) fprintf(stderr, "warning: %d imports unresolved\n", missing);
    IMAGE_NT_HEADERS32* nt = (IMAGE_NT_HEADERS32*)(uintptr_t)(APP_BASE + MEM32(APP_BASE + 0x3C));
    uint32_t entry = APP_BASE + nt->OptionalHeader.AddressOfEntryPoint;
    if (g_watchdog_s) CloseHandle(CreateThread(NULL, 0, watchdog, NULL, 0, NULL));
    if (!native32_attach_imports(APP_BASE)) return 1;
    printf("%s: %u lifted functions, entering 0x%08X\n", APP_EXE, recomp_dispatch_count, entry);
    fflush(stdout);
    native32_call_guest(entry, 0, NULL);
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
