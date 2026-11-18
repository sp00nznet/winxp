/*
 * nthost_linux: Windows 2000's own cmd.exe on its own lifted msvcrt,
 * kernel32 and ntdll, on Linux. No Wine: the guest's int 2Eh is answered on
 * POSIX by pcrecomp's runtime/native32/ntposix.c. The Linux counterpart of
 * src/nthost.c; docs/linux.md.
 *
 *   cmd-linux [--root DIR] [--sys DIR] [--nls DIR] [--cd C:\X] [-- cmd args]
 *
 *   --root  the host directory that is the guest's C:\ (default: the current directory)
 *   --sys   the rebased lifted modules, the guest's C:\WINNT\system32 (default: ROOT/sys)
 *   --nls   Windows 2000's .nls files (default: the --sys directory)
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <limits.h>
#include <sys/stat.h>
#include <pthread.h>
#include "ntposix.h"
#ifdef W2K_GUI
#include "w32kposix.h"
#endif

#define ARG(n) MEM32(g_esp + 4 + 4 * (n))
#define RET(v, n) do { g_eax = (v); g_esp += 4 + 4 * (n); } while (0)

/* What cmd.exe imports from user32 and advapi32, answered here: no window
 * station, and a registry with nothing in it (cmd's AutoRun, CompletionChar
 * and the like stay at their defaults). */
static void u_MessageBeep(void) { RET(1, 1); }
static void u_GetThreadDesktop(void) { RET(0, 1); }
static void u_GetProcessWindowStation(void) { RET(0, 0); }
static void u_GetUserObjectInformationW(void) { RET(0, 5); }
static const ntp_stub_t g_user32[] = {
    { "MessageBeep", 1, u_MessageBeep }, { "GetThreadDesktop", 1, u_GetThreadDesktop },
    { "GetProcessWindowStation", 0, u_GetProcessWindowStation },
    { "GetUserObjectInformationW", 5, u_GetUserObjectInformationW },
};
#define ERROR_FILE_NOT_FOUND 2
#define ERROR_ACCESS_DENIED 5
static void a_RegOpenKeyExW(void) { if (ARG(4)) MEM32(ARG(4)) = 0; RET(ERROR_FILE_NOT_FOUND, 5); }
static void a_RegOpenKeyW(void) { if (ARG(2)) MEM32(ARG(2)) = 0; RET(ERROR_FILE_NOT_FOUND, 3); }
static void a_RegQueryValueExW(void) { RET(ERROR_FILE_NOT_FOUND, 6); }
static void a_RegQueryValueW(void) { RET(ERROR_FILE_NOT_FOUND, 4); }
static void a_RegCloseKey(void) { RET(0, 1); }
static void a_RegCreateKeyExW(void) { RET(ERROR_ACCESS_DENIED, 9); }
static void a_RegSetValueExW(void) { RET(ERROR_ACCESS_DENIED, 6); }
static void a_RegSetValueW(void) { RET(ERROR_ACCESS_DENIED, 5); }
static void a_RegDeleteKeyW(void) { RET(ERROR_ACCESS_DENIED, 2); }
static void a_RegEnumKeyW(void) { RET(259, 4); }                 /* ERROR_NO_MORE_ITEMS */
static void a_GetSecurityInfoExW(void) { RET(1, 9); }
static const ntp_stub_t g_advapi32[] = {
    { "RegOpenKeyExW", 5, a_RegOpenKeyExW }, { "RegOpenKeyW", 3, a_RegOpenKeyW },
    { "RegQueryValueExW", 6, a_RegQueryValueExW }, { "RegQueryValueW", 4, a_RegQueryValueW },
    { "RegCloseKey", 1, a_RegCloseKey }, { "RegCreateKeyExW", 9, a_RegCreateKeyExW },
    { "RegSetValueExW", 6, a_RegSetValueExW }, { "RegSetValueW", 5, a_RegSetValueW },
    { "RegDeleteKeyW", 2, a_RegDeleteKeyW }, { "RegEnumKeyW", 4, a_RegEnumKeyW },
    { "GetSecurityInfoExW", 9, a_GetSecurityInfoExW },
};

#ifdef W2K_GUI
/* What winmine imports from the DLLs that are not lifted here: the
 * registry (its preferences: none kept, so its defaults), the About box
 * and sounds (no audio). */
static void g_RegOpenKeyExA(void) { if (ARG(4)) MEM32(ARG(4)) = 0; RET(ERROR_FILE_NOT_FOUND, 5); }
static void g_RegCreateKeyExW(void) { if (ARG(7)) MEM32(ARG(7)) = 0x80000100u; if (ARG(8)) MEM32(ARG(8)) = 1; RET(0, 9); }
static void g_RegQueryValueExA(void) { RET(ERROR_FILE_NOT_FOUND, 6); }
static void g_RegSetValueExW(void) { RET(0, 6); }
static void g_RegCreateKeyW(void) { if (ARG(2)) MEM32(ARG(2)) = 0x80000100u; RET(0, 3); }
static void g_zero1(void) { RET(0, 1); }
static void g_zero2(void) { RET(0, 2); }
static void g_zero3(void) { RET(0, 3); }
static void g_zero6(void) { RET(0, 6); }
static void g_zero4(void) { RET(0, 4); }
static void g_zero5(void) { RET(0, 5); }
static void g_enoent2(void) { RET(ERROR_FILE_NOT_FOUND, 2); }
static void g_enoent4(void) { RET(ERROR_FILE_NOT_FOUND, 4); }
static void g_enoent8(void) { RET(ERROR_FILE_NOT_FOUND, 8); }
static void g_zero0(void) { RET(0, 0); }
static const ntp_stub_t g_advapi32_gui[] = {
    { "RegOpenKeyExA", 5, g_RegOpenKeyExA }, { "RegOpenKeyExW", 5, g_RegOpenKeyExA }, { "RegCreateKeyExW", 9, g_RegCreateKeyExW },
    { "RegQueryValueExA", 6, g_RegQueryValueExA }, { "RegQueryValueExW", 6, g_RegQueryValueExA },
    { "RegSetValueExW", 6, g_RegSetValueExW }, { "RegCloseKey", 1, a_RegCloseKey },
    /* notepad, freecell */
    { "RegCreateKeyW", 3, g_RegCreateKeyW }, { "RegDeleteValueW", 2, g_zero2 }, { "RegFlushKey", 1, g_zero1 },
    { "IsTextUnicode", 3, g_zero3 },
    /* mspaint, MFC (mfc42u) */
    { "RegCreateKeyExA", 9, g_RegCreateKeyExW }, { "RegOpenKeyW", 3, a_RegOpenKeyW }, { "RegOpenKeyExW", 5, a_RegOpenKeyExW },
    { "RegEnumKeyExA", 8, g_enoent8 }, { "RegEnumKeyW", 4, g_enoent4 }, { "RegQueryValueW", 4, g_enoent4 },
    { "RegSetValueExA", 6, g_zero6 }, { "RegSetValueW", 5, g_zero5 },
    /* wordpad */
    { "RegDeleteKeyW", 2, g_enoent2 },
};
/* ole32, imm32: MFC's storage and IME calls; nothing here has either */
static void o_fail2(void) { RET(0x80004005u, 2); }
static void o_fail3(void) { RET(0x80004005u, 3); }
static void o_fail4(void) { RET(0x80004005u, 4); }
static void o_fail6(void) { RET(0x80004005u, 6); }
static const ntp_stub_t g_ole32[] = {
    { "CoTaskMemFree", 1, g_zero1 }, { "StringFromCLSID", 2, o_fail2 }, { "WriteClassStg", 2, o_fail2 },
    { "WriteFmtUserTypeStg", 3, g_zero3 }, { "OleInitialize", 1, g_zero1 }, { "OleUninitialize", 0, g_zero0 },
    /* wordpad: no compound files (each call fails) */
    { "StgOpenStorage", 6, o_fail6 }, { "OleRegGetUserType", 3, o_fail3 }, { "ReadClassStg", 2, o_fail2 },
    { "StgCreateDocfileOnILockBytes", 4, o_fail4 }, { "CreateILockBytesOnHGlobal", 3, o_fail3 }, { "ReleaseStgMedium", 1, g_zero1 },
    /* riched20 GetProcAddresses these at its first message: a name missing
     * here was a NULL call, which pops no arguments (8 bytes off the stack,
     * the heap corruption of docs/linux.md) */
    { "RegisterDragDrop", 2, g_zero2 }, { "RevokeDragDrop", 1, g_zero1 },
};
static const ntp_stub_t g_imm32[] = {
    { "ImmAssociateContext", 2, g_zero2 }, { "ImmGetCompositionStringW", 4, g_zero4 }, { "ImmGetCompositionWindow", 2, g_zero2 },
    { "ImmGetContext", 1, g_zero1 }, { "ImmNotifyIME", 4, g_zero4 }, { "ImmReleaseContext", 2, g_zero2 },
    { "ImmSetCompositionWindow", 2, g_zero2 },
};
static void s_ShellAboutW(void) { RET(1, 4); }
static void s_CommandLineToArgvW(void) {      /* (cmdline, int* argc): one argument, the whole line */
    uint32_t line = ARG(0), argc = ARG(1);
    uint32_t ga[2] = { 0, 8 };                 /* the caller GlobalFrees it: GlobalAlloc(GMEM_FIXED, 8) */
    ntp_call(ntp_export(ntp_module("kernel32.dll"), "GlobalAlloc"), 2, ga);
    uint32_t v = g_eax;
    if (v) MEM32(v) = line, MEM32(v + 4) = 0;
    if (argc) MEM32(argc) = 1;
    RET(v, 2);
}
static void s_DragQueryFileW(void) { RET(0, 4); }
static const ntp_stub_t g_shell32[] = {
    { "ShellAboutW", 4, s_ShellAboutW }, { "DragQueryFileW", 4, s_DragQueryFileW }, { "DragFinish", 1, g_zero1 },
    { "DragAcceptFiles", 2, g_zero2 }, { "CommandLineToArgvW", 2, s_CommandLineToArgvW }, { "ExtractIconW", 3, g_zero3 },
    { "SHGetSpecialFolderPathW", 4, g_zero4 },
};
/* notepad's common dialogs and printer: none here (each one cancelled) */
static void c_GetFileTitleW(void) {           /* the file part of a path into the buffer */
    uint32_t f = ARG(0), b = ARG(1), n = ARG(2), s = f;
    for (uint32_t p = f; MEM16(p); p += 2) if (MEM16(p) == '\\' || MEM16(p) == '/' || MEM16(p) == ':') s = p + 2;
    uint32_t i = 0;
    for (; MEM16(s + 2 * i) && i + 1 < n; i++) MEM16(b + 2 * i) = MEM16(s + 2 * i);
    if (n) MEM16(b + 2 * i) = 0;
    RET(0, 3);
}
static void c_PrintDlgExW(void) { RET(0x80004005u, 1); }
static const ntp_stub_t g_comdlg32[] = {
    { "FindTextW", 1, g_zero1 }, { "GetSaveFileNameW", 1, g_zero1 }, { "GetOpenFileNameW", 1, g_zero1 },
    { "PrintDlgExW", 1, c_PrintDlgExW }, { "ReplaceTextW", 1, g_zero1 }, { "GetFileTitleW", 3, c_GetFileTitleW },
    { "ChooseFontW", 1, g_zero1 }, { "PageSetupDlgW", 1, g_zero1 }, { "CommDlgExtendedError", 0, g_zero0 },
};
static const ntp_stub_t g_winspool[] = {
    { "GetPrinterDriverW", 6, g_zero6 }, { "OpenPrinterW", 3, g_zero3 }, { "ClosePrinter", 1, g_zero1 },
};
static void w_PlaySoundW(void) { RET(1, 3); }
static const ntp_stub_t g_winmm[] = { { "PlaySoundW", 3, w_PlaySoundW } };
#ifndef W2K_EXE
#define W2K_EXE "winmine.exe"
#endif
#define W2K_EXE_NAME W2K_EXE
static const struct { const char* name; uint32_t base; } g_mods[] = {
    { W2K_EXE, 0x01000000u }, { "ntdll.dll", 0x20000000u }, { "kernel32.dll", 0x20100000u }, { "msvcrt.dll", 0x20200000u },
    { "user32.dll", 0x20300000u }, { "gdi32.dll", 0x20400000u },
#ifdef W2K_CARDS
    { "cards.dll", 0x20500000u },                  /* sol, freecell */
#endif
#ifdef W2K_MFC
    { "mfc42u.dll", 0x20600000u }, { "comctl32.dll", 0x20800000u },   /* mspaint, wordpad (comctl32: MFC loads it) */
#endif
#ifdef W2K_RICHED
    { "riched20.dll", 0x20700000u },               /* wordpad */
#endif
#ifdef W2K_EXPLORER
    /* the shell (work/rebased-shell, the Win11 explorer set) and Windows 2000's own advapi32 (work/lx/reb):
     * with no host registry, its Reg* go through the guest ntdll to the registry box */
    { "comctl32.dll", 0x20800000u }, { "shlwapi.dll", 0x20900000u }, { "shell32.dll", 0x20A00000u },
    { "browseui.dll", 0x20D00000u }, { "shdocvw.dll", 0x20E00000u }, { "ole32.dll", 0x21000000u },
    { "oleaut32.dll", 0x21100000u }, { "rpcrt4.dll", 0x21200000u }, { "actxprxy.dll", 0x21300000u },
    { "clbcatq.dll", 0x21500000u }, { "mydocs.dll", 0x21600000u }, { "advapi32.dll", 0x21F00000u },
#endif
};
/* W2K_FIXED_TICK=n / W2K_FIXED_TIME=s, as on Windows (src/nthost.c): the
 * same mines and deals as the Windows runs */
static void fixed_tick(void) { g_eax = (uint32_t)strtoul(getenv("W2K_FIXED_TICK"), NULL, 0); g_esp += 4; }
static void fixed_time(void) {
    uint32_t v = (uint32_t)strtoul(getenv("W2K_FIXED_TIME"), NULL, 0), p = MEM32(g_esp + 4);
    if (p) MEM32(p) = v;
    g_eax = v;
    g_esp += 4;
}
#else
#define W2K_EXE_NAME "cmd.exe"
static const struct { const char* name; uint32_t base; } g_mods[] = {
    { "cmd.exe", 0x4AD00000u }, { "ntdll.dll", 0x20000000u }, { "kernel32.dll", 0x20100000u }, { "msvcrt.dll", 0x20200000u },
};
#endif

static int g_argc;
static char** g_argv;

#ifdef W2K_EXPLORER
#include <signal.h>
#include <sys/prctl.h>
/* CreateProcessW/A(app, cmdline, psa, tsa, inherit, flags, env, dir, si, pi): the guard's launch
 * path, as src/nthost.c's on Windows. The program must be a lifted one with a runner next to ours
 * (winmine.exe: ./winmine-linux, built from its lift); that runner starts as our child process with
 * the guest's arguments, on the same root and display, and dies with us. Anything else is refused:
 * an original Windows program never runs. ponytail: no process or thread handle (0 in both);
 * WaitForSingleObject on a child is answered when something needs it. */
static char g_root[PATH_MAX];
static int g_live;
static void host_createprocess(int ansi) {
    char name[1024] = "", args[2048] = "", stem[64], run[PATH_MAX + 80], self[PATH_MAX];
    uint32_t app = ARG(0), cl = ARG(1), pi = ARG(9);
    for (int w = 0; w < 2; w++) {                  /* the app name, else the command line's first token */
        uint32_t s = w ? cl : app;
        char* o = w ? args : name;
        size_t cap = w ? sizeof args : sizeof name, n = 0;
        if (!s) continue;
        for (uint32_t c; n < cap - 1 && (c = ansi ? MEM8(s + n) : MEM16(s + 2 * n)); n++) o[n] = c < 0x80 ? (char)c : '?';
        o[n] = 0;
    }
    const char* a = args;
    while (*a == ' ') a++;
    const char* t0 = a, *t1;
    if (*a == '"') { t0 = ++a; t1 = strchr(a, '"'); a = t1 ? t1 + 1 : a + strlen(a); if (!t1) t1 = a; }
    else { while (*a && *a != ' ') a++; t1 = a; }
    if (!name[0]) snprintf(name, sizeof name, "%.*s", (int)(t1 - t0), t0);
    const char* b = name;
    for (const char* p = name; *p; p++) if (*p == '\\' || *p == '/' || *p == ':') b = p + 1;
    size_t k = 0;
    for (; b[k] && b[k] != '.' && k < sizeof stem - 1; k++) stem[k] = (char)(b[k] >= 'A' && b[k] <= 'Z' ? b[k] + 32 : b[k]);
    stem[k] = 0;
    ssize_t sl = readlink("/proc/self/exe", self, sizeof self - 1);
    self[sl > 0 ? sl : 0] = 0;
    char* d = strrchr(self, '/');
    if (d) *d = 0;
    snprintf(run, sizeof run, "%s/%s-linux", self, stem);
    int ok = k && strspn(stem, "abcdefghijklmnopqrstuvwxyz0123456789_") == k && !access(run, X_OK)
             && (!b[k] || !strcasecmp(b + k, ".exe"));
    if (!ok) {
        fprintf(stderr, "[guard] %s: a program that is not lifted: not run\n", name);
        g_eax = 0, g_esp += 4 + 40;
        return;
    }
    while (*a == ' ') a++;
    fprintf(stderr, "[launch] %s -> %s %s\n", name, run, a);
    /* live: the child draws into our X window (w32kposix's shared surface, in the scratch
     * directory: the root's parent), not into one of its own */
    static int seq;
    char shm[PATH_MAX + 64];
    snprintf(shm, sizeof shm, "%s/../w2k-ipc-%d-%d.fb", g_root, (int)getpid(), seq++);
    int kc = g_live ? w2kx_child(shm) : -1;
    pid_t pid = fork();
    if (pid == 0) {
        prctl(PR_SET_PDEATHSIG, SIGTERM);
        if (kc >= 0) setenv("W2K_SHM", shm, 1); else unsetenv("W2K_SHM");
        if (chdir(g_root)) _exit(127);
        char* av[] = { run, "--root", g_root, g_live ? "--live" : "--mute", *a ? "--" : NULL, (char*)a, NULL };
        if (!*a) av[4] = NULL;
        execv(run, av);
        _exit(127);
    }
    if (kc >= 0 && pid > 0) w2kx_child_pid(kc, (int)pid);
    if (pi) MEM32(pi) = 0, MEM32(pi + 4) = 0, MEM32(pi + 8) = (uint32_t)pid, MEM32(pi + 12) = (uint32_t)pid;
    g_eax = pid > 0, g_esp += 4 + 40;
}
/* GetUserNameW/A(buf, size*): advapi32 asks LSA (an RPC to \PIPE\lsarpc), and no LSA runs here.
 * The profile's user: "user" (USERNAME in the guest's environment, the box's profile folders). */
static void host_getusername(int ansi) {
    uint32_t b = ARG(0), n = ARG(1);
    if (!n || MEM32(n) < 5) { if (n) MEM32(n) = 5; g_eax = 0, g_esp += 12; return; }
    for (int i = 0; i < 5; i++) { char c = "user"[i]; if (ansi) MEM8(b + i) = (uint8_t)c; else MEM16(b + 2 * i) = (uint8_t)c; }
    MEM32(n) = 5;
    g_eax = 1, g_esp += 12;
}
static void host_getusernamew(void) { host_getusername(0); }
static void host_getusernamea(void) { host_getusername(1); }
static void host_createprocessw(void) { host_createprocess(0); }
static void host_createprocessa(void) { host_createprocess(1); }
#endif

static void* host_main(void* rcp) {
    char root[PATH_MAX], sys[PATH_MAX] = "", nls[PATH_MAX] = "", cd[1024] = "", cmdline[4096] = "C:\\WINNT\\system32\\" W2K_EXE_NAME;
#ifdef W2K_GUI
    char names[PATH_MAX + 64] = "", fonts[PATH_MAX] = "";
    int scx = 1024, scy = 768;
#endif
    if (!getcwd(root, sizeof root)) strcpy(root, ".");
    for (int i = 1, n; i < g_argc; i++) {
        if (!strcmp(g_argv[i], "--root") && i + 1 < g_argc) { if (!realpath(g_argv[++i], root)) { perror(g_argv[i]); exit(1); } }
        else if (!strcmp(g_argv[i], "--sys") && i + 1 < g_argc) { if (!realpath(g_argv[++i], sys)) { perror(g_argv[i]); exit(1); } }
        else if (!strcmp(g_argv[i], "--nls") && i + 1 < g_argc) { if (!realpath(g_argv[++i], nls)) { perror(g_argv[i]); exit(1); } }
        else if (!strcmp(g_argv[i], "--cd") && i + 1 < g_argc) snprintf(cd, sizeof cd, "%s", g_argv[++i]);
        else if (!strcmp(g_argv[i], "--mute")) ;          /* nothing makes a sound here */
        else if (!strcmp(g_argv[i], "--regbox") && i + 1 < g_argc) ntp_regbox(g_argv[++i]);   /* the registry box file */
#ifdef W2K_GUI
        else if (!strcmp(g_argv[i], "--names") && i + 1 < g_argc) snprintf(names, sizeof names, "%s", g_argv[++i]);
        else if (!strcmp(g_argv[i], "--fonts") && i + 1 < g_argc) snprintf(fonts, sizeof fonts, "%s", g_argv[++i]);
        else if (!strcmp(g_argv[i], "--screen") && i + 1 < g_argc) sscanf(g_argv[++i], "%dx%d", &scx, &scy);
        else if ((n = w2kx_script_arg(g_argc, g_argv, i))) i += n - 1;
#endif
        else if (!strcmp(g_argv[i], "--")) {
            while (++i < g_argc) { strncat(cmdline, " ", sizeof cmdline - strlen(cmdline) - 1); strncat(cmdline, g_argv[i], sizeof cmdline - strlen(cmdline) - 1); }
            break;
        } else { fprintf(stderr, "usage: cmd-linux [--root DIR] [--sys DIR] [--nls DIR] [--cd C:\\X] [-- args]\n"); exit(1); }
    }
    if (!sys[0]) snprintf(sys, sizeof sys, "%s/sys", root);
    if (!nls[0]) snprintf(nls, sizeof nls, "%s", sys);
    if (!cd[0]) {                    /* the host's current directory, if it is under the root */
        char here[PATH_MAX];
        size_t n = strlen(root);
        if (getcwd(here, sizeof here) && !strncmp(here, root, n) && (here[n] == '/' || !here[n])) {
            snprintf(cd, sizeof cd, "C:\\%s", here[n] ? here + n + 1 : "");
            for (char* p = cd; *p; p++) if (*p == '/') *p = '\\';
        } else strcpy(cd, "C:\\");
    }

    ntp_init();
    ntp_mount("C:", root);
    ntp_mount("C:\\WINNT\\system32", sys);
    {   /* the mount point's own directories under C:\, as on a real drive: a search of C:\ for WINNT
         * (FindFirstFile, shell32's link resolver walking C:\WINNT\system32\notepad.exe) found none */
        char p[PATH_MAX + 32];
        snprintf(p, sizeof p, "%s/WINNT", root), mkdir(p, 0755);
        snprintf(p, sizeof p, "%s/WINNT/system32", root), mkdir(p, 0755);
    }
    for (size_t i = 0; i < sizeof g_mods / sizeof g_mods[0]; i++) {
        char p[PATH_MAX + 64];
        snprintf(p, sizeof p, "%s/%s", sys, g_mods[i].name);
        if (getenv("W2K_SKIP") && strstr(getenv("W2K_SKIP"), g_mods[i].name)) continue;   /* (W2K_SKIP=a.dll,b.dll: not mapped) */
        if (!ntp_map(p, g_mods[i].base, g_mods[i].name)) exit(1);
    }
#ifdef W2K_GUI
    (void)g_user32, (void)g_advapi32;
#ifdef W2K_EXPLORER
    (void)g_advapi32_gui, (void)g_shell32, (void)g_ole32;   /* all three lifted */
#else
    ntp_proxy("advapi32.dll", g_advapi32_gui, sizeof g_advapi32_gui / sizeof g_advapi32_gui[0]);
    ntp_proxy("shell32.dll", g_shell32, sizeof g_shell32 / sizeof g_shell32[0]);
    ntp_proxy("ole32.dll", g_ole32, sizeof g_ole32 / sizeof g_ole32[0]);
#endif
    ntp_proxy("winmm.dll", g_winmm, 1);
    ntp_proxy("imm32.dll", g_imm32, sizeof g_imm32 / sizeof g_imm32[0]);
    ntp_proxy("comdlg32.dll", g_comdlg32, sizeof g_comdlg32 / sizeof g_comdlg32[0]);
    ntp_proxy("winspool.drv", g_winspool, sizeof g_winspool / sizeof g_winspool[0]);
    ntp_syscalls(0x20000000u);
    {   /* user32 and gdi32 lifted too: win32k is pcrecomp's w32kposix.c */
        uint32_t w[2] = { 0x20300000u, 0x20400000u };
        if (!names[0]) snprintf(names, sizeof names, "%s/win32k_2000sp4.txt", sys);
        if (!fonts[0]) snprintf(fonts, sizeof fonts, "%s", sys);
        ntp_win32k(w, 2, names);
        w2kx_install(scx, scy, fonts);
        ntp_clock_virtual();
    }
#else
    ntp_proxy("user32.dll", g_user32, sizeof g_user32 / sizeof g_user32[0]);
    ntp_proxy("advapi32.dll", g_advapi32, sizeof g_advapi32 / sizeof g_advapi32[0]);
    ntp_syscalls(0x20000000u);
#endif
    {   /* csrss's \NLS sections, from Windows 2000's own NLS files */
        static const char* sec[][2] = {
            { "\\NLS\\NlsSectionUnicode", "unicode.nls" }, { "\\NLS\\NlsSectionCType", "ctype.nls" },
            { "\\NLS\\NlsSectionLocale", "locale.nls" }, { "\\NLS\\NlsSectionSortkey", "sortkey.nls" },
            { "\\NLS\\NlsSectionSortTbls", "sorttbls.nls" }, { "\\NLS\\NlsSectionCP1252", "c_1252.nls" },
            { "\\NLS\\NlsSectionCP437", "c_437.nls" }, { "\\NLS\\NlsSectionLANG_INTL", "l_intl.nls" },
            { "\\NLS\\NlsSectionSortkey00000409", "sortkey_00000409.nls" },
        };
        for (size_t i = 0; i < sizeof sec / sizeof sec[0]; i++) {
            char f[PATH_MAX + 64];
            snprintf(f, sizeof f, "%s/%s", nls, sec[i][1]);
            ntp_section_file(sec[i][0], f);
        }
    }
    uint32_t exe = g_mods[0].base;
    if (!ntp_boot(0x20000000u, exe, "C:\\WINNT\\system32\\" W2K_EXE_NAME, cmdline, "C:\\WINNT\\system32;C:\\WINNT", cd, nls, 0x0400))
        exit(1);
    uint32_t entry = exe + MEM32(exe + MEM32(exe + 0x3C) + 0x28);
#ifdef W2K_GUI
    if (getenv("W2K_FIXED_TICK")) ntp_replace(ntp_export(0x20100000u, "GetTickCount"), fixed_tick);
    if (getenv("W2K_FIXED_TIME")) ntp_replace(ntp_export(0x20200000u, "time"), fixed_time);
    w2kx_start();
#endif
#ifdef W2K_EXPLORER
    snprintf(g_root, sizeof g_root, "%s", root);
    for (int i = 1; i < g_argc; i++) if (!strcmp(g_argv[i], "--live")) g_live = 1;
    signal(SIGCHLD, SIG_IGN);                      /* the children reap themselves */
    ntp_replace(ntp_export(0x20100000u, "CreateProcessW"), host_createprocessw);
    ntp_replace(ntp_export(0x20100000u, "CreateProcessA"), host_createprocessa);
    ntp_replace(ntp_export(0x21F00000u, "GetUserNameW"), host_getusernamew);
    ntp_replace(ntp_export(0x21F00000u, "GetUserNameA"), host_getusernamea);
#endif
    fprintf(stderr, "%s: %u lifted functions, entering 0x%08X\n", W2K_EXE_NAME, recomp_dispatch_count, entry);
    ntp_call(entry, 0, NULL);
    *(int*)rcp = (int)g_eax;
    return NULL;
}

int main(int argc, char** argv) {
    pthread_attr_t at;
    pthread_t t;
    int rc = 1;
    g_argc = argc, g_argv = argv;
    setvbuf(stderr, NULL, _IONBF, 0);
    pthread_attr_init(&at);
    pthread_attr_setstacksize(&at, 256u << 20);    /* lifted calls nest on the host stack */
    if (pthread_create(&t, &at, host_main, &rc)) return 1;
    pthread_join(t, NULL);
    return rc;
}
