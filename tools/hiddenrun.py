"""hiddenrun.py - run a program on a private, invisible desktop and screenshot its windows.

    python tools/hiddenrun.py --secs 30 --shot 10 --shot 25 --out out/run -- build/johnny.exe /s

Nothing appears on the real screens. Each --shot T writes <out>_T.png: every
visible top-level window of the process, read from its window DC, pasted at its screen position. Stdout/stderr of the
program go to <out>.log. The process tree is killed at --secs.
"""
import argparse, os, ctypes, ctypes.wintypes as W, subprocess, time
from PIL import Image

u32, k32, g32 = ctypes.windll.user32, ctypes.windll.kernel32, ctypes.windll.gdi32
u32.CreateDesktopW.restype = W.HANDLE


def windows_of(pid, desk):
    out = []
    cb = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def f(h, _):
        p = W.DWORD(); u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        # Windows 11 adds its UAC input indicator windows (UAC_InputIndicator*,
        # in the program's own process): not the program's
        b = ctypes.create_unicode_buffer(64); u32.GetClassNameW(h, b, 64)
        if p.value != os.getpid() and u32.IsWindowVisible(h) and not b.value.startswith('UAC'):   # the private desktop holds only the run's process tree (hold_image relaunches)
            out.append(h)
        return True
    u32.EnumDesktopWindows(W.HANDLE(desk), cb(f), 0)
    return out


def grab(h):
    r = W.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
    w, hh = r.right - r.left, r.bottom - r.top
    if w <= 0 or hh <= 0:
        return None, r
    # (the window DC only makes a compatible bitmap; the capture is PrintWindow)
    sdc = u32.GetWindowDC(h); mdc = g32.CreateCompatibleDC(sdc)
    bmp = g32.CreateCompatibleBitmap(sdc, w, hh); g32.SelectObject(mdc, bmp)
    # PrintWindow renders the window alone; a BitBlt from its DC also reads
    # whatever screen pixels lie under it (the user's desktop).
    u32.PrintWindow(h, mdc, 2)   # PW_RENDERFULLCONTENT
    buf = ctypes.create_string_buffer(w * hh * 4)
    bi = (ctypes.c_uint32 * 10)(40, w, (-hh) & 0xFFFFFFFF, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
    g32.GetDIBits(mdc, bmp, 0, hh, buf, bi, 0)
    g32.DeleteObject(bmp); g32.DeleteDC(mdc); u32.ReleaseDC(h, sdc)
    return Image.frombuffer('RGBA', (w, hh), buf, 'raw', 'BGRA', 0, 1).convert('RGB'), r


class STARTUPINFO(ctypes.Structure):
    _fields_ = [('cb', W.DWORD), ('lpReserved', W.LPWSTR), ('lpDesktop', W.LPWSTR), ('lpTitle', W.LPWSTR),
                ('x', W.DWORD), ('y', W.DWORD), ('cx', W.DWORD), ('cy', W.DWORD), ('cxc', W.DWORD),
                ('cyc', W.DWORD), ('fill', W.DWORD), ('dwFlags', W.DWORD), ('wShow', W.WORD),
                ('cb2', W.WORD), ('r2', ctypes.c_void_p), ('hIn', W.HANDLE), ('hOut', W.HANDLE), ('hErr', W.HANDLE)]


class PI(ctypes.Structure):
    _fields_ = [('hProcess', W.HANDLE), ('hThread', W.HANDLE), ('pid', W.DWORD), ('tid', W.DWORD)]


class Proc:
    def __init__(s, pi): s.h, s.pid = pi.hProcess, pi.pid
    def poll(s):
        c = W.DWORD(); k32.GetExitCodeProcess(s.h, ctypes.byref(c))
        return None if c.value == 259 else c.value


def launch(cmd, desktop, logpath):
    import msvcrt, os
    log = open(logpath, 'w')
    h = msvcrt.get_osfhandle(log.fileno())
    os.set_handle_inheritable(h, True)
    si = STARTUPINFO(); si.cb = ctypes.sizeof(si); si.lpDesktop = desktop
    si.dwFlags = 0x100; si.hOut = si.hErr = h
    pi = PI()
    if not k32.CreateProcessW(None, ctypes.create_unicode_buffer(subprocess.list2cmdline(cmd)),
                              None, None, True, 0, None, None, ctypes.byref(si), ctypes.byref(pi)):
        raise OSError(ctypes.GetLastError())
    return Proc(pi)


def preview_window(desk, w, h):
    """A plain window standing in for the Control Panel's preview box, owned
    by a thread on the hidden desktop that keeps pumping its messages."""
    import threading
    got = []
    def run():
        u32.SetThreadDesktop(W.HANDLE(desk))
        u32.CreateWindowExW.restype = W.HWND
        hw = u32.CreateWindowExW(0, 'STATIC', 'preview', 0x10000000 | 0x00800000, 50, 50, w, h,
                                 None, None, None, None)   # WS_VISIBLE | WS_BORDER
        got.append(hw)
        msg = W.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u32.TranslateMessage(ctypes.byref(msg)); u32.DispatchMessageW(ctypes.byref(msg))
    threading.Thread(target=run, daemon=True).start()
    while not got:
        time.sleep(0.05)
    return got[0]


def main():
    # No loader or fault box from a child may reach the user's real desktop
    # (csrss shows "Entry Point Not Found" on the interactive desktop whatever
    # desktop the child runs on): FAILCRITICALERRORS | NOGPFAULTERRORBOX |
    # NOOPENFILEERRORBOX, inherited by every child (no CREATE_DEFAULT_ERROR_MODE).
    k32.SetErrorMode(0x8003)
    ap = argparse.ArgumentParser()
    ap.add_argument('--secs', type=float, default=30)
    ap.add_argument('--shot', type=float, action='append', default=[])
    ap.add_argument('--out', default='out/run')
    ap.add_argument('--preview', metavar='WxH', help='make a window this size on the hidden desktop '
                    'and pass its handle where the command says {hwnd} (a screen saver /p)')
    ap.add_argument('--end-at', type=float, help='at this second, close the preview window (--preview) '
                    'or press a key in the window of the program, as a person ending a screen saver would')
    ap.add_argument('--click', action='append', default=[], help='X,Y@T: a left click posted to the main '
                    'window at client X,Y, T seconds in')
    ap.add_argument('--command', action='append', default=[], help='ID@T: WM_COMMAND ID posted to the main window')
    ap.add_argument('--post', action='append', default=[], help='MSG,WPARAM,LPARAM@T: any message posted to the '
                    'main window (0x112,0xF100,0x67@T: WM_SYSCOMMAND SC_KEYMENU, the menu of the letter g)')
    ap.add_argument('--type', action='append', default=[], help='ID=TEXT@T: typed into control ID of the top window '
                    '(a dialog): EM_SETSEL all, then a posted WM_CHAR per character')
    ap.add_argument('--dlgcommand', action='append', default=[], help='ID@T: WM_COMMAND ID posted to the top window')
    ap.add_argument('--drag', action='append', default=[], help='X1,Y1,X2,Y2@T: a left-button drag in the main '
                    'window client coordinates, posted to the deepest child under X1,Y1')
    ap.add_argument('--dblclick', action='append', default=[], help='[TITLE:]X,Y@T: a double click (down, up, '
                    'WM_LBUTTONDBLCLK, up: what the system makes of two real clicks) to the deepest child under X,Y')
    ap.add_argument('--childpost', action='append', default=[], help='X,Y:MSG,WPARAM,LPARAM@T: a message posted '
                    'to the deepest child under X,Y of the main window; CLASS:MSG,... to its child of that class')
    ap.add_argument('--settle', action='store_true', help='event-driven: each step waits until the previous one '
                    'has settled (WM_NULL answered, nothing left to paint, pixels held --hold s); step times are limits')
    ap.add_argument('--hold', type=float, default=0.5)
    ap.add_argument('--still-crop', type=int, default=0, help='with --settle: leave this many bottom rows out of '
                    'the pixel check (a status bar clock, as the Time: of sol)')
    ap.add_argument('--scale', type=float, default=1, help='with --settle: each step limit is its time x this')
    ap.add_argument('cmd', nargs=argparse.REMAINDER)
    a = ap.parse_args(); a.stop = False
    cmd = a.cmd[1:] if a.cmd[:1] == ['--'] else a.cmd
    name = os.environ.get('HIDDENRUN_DESKTOP', 'pcrecomp_hidden')   # another run's windows (another tool's hiddenrun) stay off this one's
    desk = u32.CreateDesktopW(name, None, None, 0, 0x10000000, None)
    if a.preview:
        hwnd = a.preview_hwnd = preview_window(desk, *map(int, a.preview.split('x')))
        cmd = [c.replace('{hwnd}', str(hwnd)) for c in cmd]
    p = launch(cmd, name, a.out + '.log')
    t0 = time.time()
    import threading
    th = threading.Thread(target=timeline, args=(a, p, desk, t0)); th.start()
    while th.is_alive() and time.time() - t0 < a.secs and p.poll() is None:
        time.sleep(0.2)
    a.stop = True; th.join()
    print('exit', p.poll(), f'after {time.time() - t0:.1f}s')
    subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)], capture_output=True)
    u32.CloseDesktop(desk)


def deepest(h, x, y):
    """The deepest visible child of h under client X,Y, and the point in its client coordinates."""
    u32.ChildWindowFromPointEx.restype = W.HWND
    pt = W.POINT(x, y)
    while True:
        c = u32.ChildWindowFromPointEx(h, pt, 1)
        if not c or c == h: return h, pt
        u32.MapWindowPoints(h, c, ctypes.byref(pt), 1); h = c


def send_input(a, p, desk, kind, what):
    ws = windows_of(p.pid, desk)
    main_w = ws[-1] if ws else None          # top-level, bottom of the z-order: the main window
    if kind == 'end':
        for h in ([a.preview_hwnd] if a.preview else ws):
            if a.preview: u32.PostMessageW(h, 0x0010, 0, 0)                 # WM_CLOSE
            else: u32.PostMessageW(h, 0x0100, 0x20, 0x00390001)             # WM_KEYDOWN space
    elif main_w and kind == 'click':
        x, y = map(int, what.split(','))
        lp = (y << 16) | (x & 0xFFFF)
        u32.PostMessageW(main_w, 0x0201, 1, lp)   # WM_LBUTTONDOWN, MK_LBUTTON
        u32.PostMessageW(main_w, 0x0202, 0, lp)   # WM_LBUTTONUP
    elif main_w and kind == 'childpost':
        xy, m = what.split(':')
        if xy[0].isdigit(): h, _ = deepest(main_w, *map(int, xy.split(',')))
        elif xy[0] == '~':   # ~CLASS: the first descendant of that class (a control under a group box)
            found = []
            P = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
            def f(c, _):
                b = ctypes.create_unicode_buffer(64); u32.GetClassNameW(c, b, 64)
                if b.value.lower() == xy[1:].lower(): found.append(c); return False
                return True
            u32.EnumChildWindows(main_w, P(f), 0)
            if not found: print('childpost: no', xy); return
            h = found[0]
        else: u32.FindWindowExW.restype = W.HWND; h = u32.FindWindowExW(main_w, None, xy, None)   # a class: a screen window
        u32.PostMessageW(h, *(int(v, 0) for v in m.split(',')))
    elif main_w and kind == 'drag':
        x1, y1, x2, y2 = map(int, what.split(','))
        h, pt = deepest(main_w, x1, y1)
        dx, dy = pt.x - x1, pt.y - y1
        for i in range(11):
            x, y = x1 + (x2 - x1) * i // 10 + dx, y1 + (y2 - y1) * i // 10 + dy
            lp = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
            u32.PostMessageW(h, 0x0201 if i == 0 else 0x0200, 1, lp)   # WM_LBUTTONDOWN, then WM_MOUSEMOVE
        u32.PostMessageW(h, 0x0202, 0, lp)                              # WM_LBUTTONUP
    elif main_w and kind == 'dblclick':
        if ':' in what:                                          # TITLE:X,Y, in the client of the screen's window TITLE
            title, xy = what.rsplit(':', 1)
            u32.FindWindowExW.restype = W.HWND
            w = u32.FindWindowExW(main_w, None, None, title)
            if not w: print('dblclick: no window', title); return
            pt = W.POINT(*map(int, xy.split(','))); u32.MapWindowPoints(w, main_w, ctypes.byref(pt), 1)
            what = '%d,%d' % (pt.x, pt.y)
        h, pt = deepest(main_w, *map(int, what.split(',')))
        lp = ((pt.y & 0xFFFF) << 16) | (pt.x & 0xFFFF)
        for m, wp in ((0x0201, 1), (0x0202, 0), (0x0203, 1), (0x0202, 0)): u32.PostMessageW(h, m, wp, lp)
    elif ws and kind == 'type':
        cid, text = what.split('=', 1)
        u32.GetDlgItem.restype = W.HWND
        e = u32.GetDlgItem(ws[0], int(cid, 0))
        u32.FindWindowExW.restype = W.HWND
        for _ in range(3):                                       # a combo box: its Edit (Open dialog)
            sub = u32.FindWindowExW(e, None, 'Edit', None) or u32.FindWindowExW(e, None, 'ComboBox', None)
            if not sub: break
            e = sub
        u32.PostMessageW(e, 0x00B1, 0, -1)                    # EM_SETSEL all
        for ch in text: u32.PostMessageW(e, 0x0102, ord(ch), 1)  # WM_CHAR
    elif ws and kind == 'dlgcmd':
        u32.PostMessageW(ws[0], 0x0111, int(what, 0), 0)
    elif main_w and kind == 'post':
        m, wp, lp = (int(v, 0) for v in what.split(','))
        u32.PostMessageW(main_w, m, wp, lp)
    elif main_w and kind == 'cmd':
        u32.PostMessageW(main_w, 0x0111, int(what, 0), 0)   # WM_COMMAND


def busy(h):
    """h or a visible child has something left to paint, or h's thread does
    not answer a sent WM_NULL within 250 ms."""
    r = ctypes.c_size_t()
    if not u32.SendMessageTimeoutW(h, 0, 0, 0, 0x3, 250, ctypes.byref(r)):   # SMTO_BLOCK|SMTO_ABORTIFHUNG
        return True
    if u32.GetUpdateRect(h, None, 0):
        return True
    left = []
    cb = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def f(c, _):
        if u32.IsWindowVisible(c) and u32.GetUpdateRect(c, None, 0): left.append(c)
        return True
    u32.EnumChildWindows(h, cb(f), 0)
    return bool(left)


def settle(a, p, desk, deadline):
    """Wait until the run's windows exist, answer WM_NULL, have nothing left
    to paint, and show the same pixels as at least a.hold seconds before (a
    capture that differs and then comes back, as PrintWindow sometimes reads
    a grid mid-repaint, does not restart the wait); or until the deadline.
    The settled image, or None."""
    seen = []   # (time, checked crop, image, key) since the windows were last busy
    u32.WaitForInputIdle(p.h, max(0, int((deadline - time.time()) * 1000)))   # start-up: the first idle (later calls return at once)
    while time.time() < deadline and p.poll() is None and not a.stop:
        hs = [a.preview_hwnd] if a.preview else windows_of(p.pid, desk)
        if not hs or any(busy(h) for h in hs):
            seen = []; time.sleep(0.1); continue
        img, now = compose(hs), time.time()
        if img is not None:
            c = img.crop((0, 0, img.size[0], max(1, img.size[1] - a.still_crop)))
            seen.append((now, c, img, (c.size, c.tobytes())))
            if any(now - t >= a.hold and k == seen[-1][3] for t, _, _, k in seen[:-1]):
                # the capture seen most often: PrintWindow reads some windows
                # (packager's panes) half-drawn now and then, whatever the wait
                keys = [k for *_, k in seen]
                return max(seen, key=lambda e: keys.count(e[3]))[2]
        time.sleep(0.1)
    return None


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [('cbSize', W.DWORD), ('flags', W.DWORD), ('hwndActive', W.HWND), ('hwndFocus', W.HWND),
                ('hwndCapture', W.HWND), ('hwndMenuOwner', W.HWND), ('hwndMoveSize', W.HWND),
                ('hwndCaret', W.HWND), ('rcCaret', W.RECT)]


def active_of(h):
    """The active window of h's thread (any desktop)."""
    g = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    tid = u32.GetWindowThreadProcessId(h, None)
    return g.hwndActive if u32.GetGUIThreadInfo(tid, ctypes.byref(g)) else None


def in_menu(h):
    """h's thread is in menu mode (GUI_INMENUMODE)."""
    g = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    return bool(u32.GetGUIThreadInfo(u32.GetWindowThreadProcessId(h, None), ctypes.byref(g)) and g.flags & 4)


def compose(hs):
    shots = [grab(h) for h in hs]
    shots = [s for s in shots if s[0]]
    if not shots:
        return None
    x0 = min(r.left for _, r in shots); y0 = min(r.top for _, r in shots)
    W_ = max(r.right for _, r in shots) - x0; H_ = max(r.bottom for _, r in shots) - y0
    canvas = Image.new('RGB', (W_, H_))
    for img, r in reversed(shots):   # EnumWindows is top-first; paint bottom-up
        canvas.paste(img, (r.left - x0, r.top - y0))
    return canvas


def timeline(a, p, desk, t0):
    # GDI reads across desktops come back black: capture from a thread that
    # has joined the hidden desktop. Inputs and shots run here as one ordered
    # list. With --settle each step first waits for the previous one to
    # settle, and its time (x --scale) is only an upper limit; without, each
    # fires at its time.
    u32.SetThreadDesktop(W.HANDLE(desk))
    ev = sorted([(float(c.split('@')[1]), 1, k, c.split('@')[0]) for opt, k in
                 ((a.click, 'click'), (a.command, 'cmd'), (a.post, 'post'), (a.type, 'type'),
                  (a.dlgcommand, 'dlgcmd'), (a.drag, 'drag'), (a.dblclick, 'dblclick'), (a.childpost, 'childpost')) for c in opt] +
                [(t, 0, 'shot', '') for t in a.shot] +
                ([(a.end_at, 2, 'end', '')] if a.end_at is not None else []))
    for t, _, kind, what in ev:
        if a.settle:
            img = settle(a, p, desk, t0 + t * a.scale)
            how = 'settled' if img else 'LIMIT'
        else:
            how, img = 'at time', None
            while time.time() - t0 < t and p.poll() is None and not a.stop:
                time.sleep(0.05)
        if p.poll() is not None or a.stop:
            print(f'{t}s: process gone before {kind}'); return
        stamp = f'{t}s at {time.time() - t0:.1f}s ({how})'
        if kind != 'shot':
            send_input(a, p, desk, kind, what); print(f'{stamp}: {kind} {what}'); continue
        hs = [a.preview_hwnd] if a.preview else windows_of(p.pid, desk)
        # the top window active, so its menu bar and caption are drawn active
        # whatever the run's timing left (an inactive menu bar: a flake)
        # (GetForegroundWindow answers for the input desktop only, so it never
        # matched here; the window's thread says whether it is active. On a
        # loaded machine wait for the activation, then for the repaint.)
        # An open menu (its thread in menu mode) is left alone: activating
        # closes it.
        if hs and not a.preview and active_of(hs[0]) != hs[0] and not in_menu(hs[0]):
            u32.SetForegroundWindow(hs[0])
            for _ in range(20):
                if active_of(hs[0]) == hs[0]: break
                time.sleep(0.05)
            if a.settle: img = settle(a, p, desk, time.time() + 3)
            else: time.sleep(0.3)
            hs = windows_of(p.pid, desk)
        canvas = img or compose(hs)   # the settled pixels, not a fresh read that may catch a repaint
        if canvas is None:
            print(f'{stamp}: no window'); continue
        if os.environ.get('HIDDENRUN_RECTS'):
            for h in hs:
                r = W.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
                print(f'  window {r.left},{r.top} {r.right - r.left}x{r.bottom - r.top}')
        path = f'{a.out}_{int(t)}.png'; canvas.save(path); print(f'{stamp}: {path} {canvas.size}')


if __name__ == '__main__':
    main()
