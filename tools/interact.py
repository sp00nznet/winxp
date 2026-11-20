#!/usr/bin/env python3
"""Drive an accessory the same way on its stage 1 build (host user32/gdi32) and
on build/nt<app>.exe (Windows 2000's own user32/gdi32, lifted), and compare a
screenshot after each step pixel by pixel.

    py -3 tools/interact.py [winmine|notepad|calc ...]   (all three by default)
BUILD_DIR=build-x (build.cmd's) drives another build of the same tree.
winmine: start, a click on a cell, Game > Intermediate, Game > Custom (dialog);
then, in runs of their own, the Custom dialog driven, the Game menu open
(WM_SYSCOMMAND SC_KEYMENU 'g'), at start and after Game > Intermediate.
notepad: start, text typed into its edit control (WM_CHAR).
calc: start, 12+3= pressed (WM_COMMAND with the buttons' IDs).
The mines are the same in both (W2K_FIXED_TICK: winmine seeds with
GetTickCount). Shots: shots/<run>_<build>_<t>.png.
Two columns, both checks: "stage1" (the lifted shot against the stage 1 build's,
always on, any display; no stage 1 build only skips it; informational for
mspaint/wordpad, whose lifted builds load Windows 2000's own comctl32) and "golden" (against
the approved golden for this display). Goldens are kept per display, screen size
and DPI (e.g. 3840x2160@192): shots/golden/<display>/ (local) and that key in
tools/golden.json (committed, each golden's RGB sha256). The exit code is 1 when
a lifted shot differs from either. With no goldens for this display the golden
column says "SKIP: no golden for this display"; that fails only with --strict.
Approve (after checking the new lifted shots by eye with the Read tool, and
against stage 1 at 0 px):
    py -3 tools/interact.py --approve [app ...]
which copies this run's lifted shots to shots/golden/<display> and rewrites
their hashes under this display's key.
Event-driven (hiddenrun --settle): each step waits for the previous one to
settle; the step times (x2) are only limits. sol's status bar (Time:, the host
build's own clock) is left out of the check and the comparison.
"""
import os, subprocess, sys
import ctypes
ctypes.windll.kernel32.SetErrorMode(0x8003)   # no loader/fault box on the real desktop (inherited)
from PIL import Image, ImageChops
Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.environ.get('BUILD_DIR', 'build')   # (build.cmd's: another build of the same tree, as win2000's)
CALC = {c: 0x7C + int(c) for c in '0123456789'}
CALC.update({'+': 0x5C, '-': 0x5D, '*': 0x5B, '/': 0x5A, '=': 0x70})
APPS = {
    'winmine': [('int', [('start', 4, []), ('click', 5.4, ['--click', '30,80@5']), ('intermediate', 8, ['--command', '522@7']),
                         ('custom', 10, ['--command', '524@9'])]),
                ('dlg', [('custom 20x30', 8, ['--command', '524@3', '--type', '0x8D=20@4', '--type', '0x8E=30@5',
                                             '--dlgcommand', '1@6'])]),
                ('menu', [('menu open', 5, ['--post', '0x112,0xF100,0x67@3'])]),
                ('menu2', [('menu, Interm.', 7, ['--command', '522@3', '--post', '0x112,0xF100,0x67@5'])])],
    # notepad's stage 1 build takes ~6 s to show its window (host comdlg32, shell32)
    'notepad': [('np', [('start', 9, []), ('typed', 11, ['--type', '15=Hello, Windows XP@9.5'])])],
    'sol': [('sol', [('deal', 8, []), ('deck click', 10, ['--click', '40,60@9'])])],
    'freecell': [('fc', [('deal', 8, ['--command', '102@3']), ('card to cell', 11, ['--click', '40,300@9', '--click', '40,50@10'])])],
    'packager': [('pk', [('start', 6, [])])],
    'mspaint': [('paint', [('start', 9, []), ('line', 11, ['--drag', '100,100,250,180@9.5'])])],
    'wordpad': [('wp', [('start', 9, []), ('typed', 11, ['--type', '0xE900=Hello, Windows XP@9.5'])])],
    'charmap': [('cm', [('start', 6, [])])],
    'calc': [('calc', [('start', 5, []),
                       ('12+3=', 8, sum((['--command', '%d@%.1f' % (CALC[c], 5.5 + 0.3 * i)] for i, c in enumerate('12+3=')), []))])],
}
# ponytail: these paint a last piece >1.5 s after going still (sol's last card flip, freecell's
# Cards Left, packager's Appearance pane); a longer hold, not a per-app wait
SLOW = ('sol', 'freecell', 'packager')
S1_DIFFERS = ('mspaint', 'wordpad')   # stage 1 column informational only for these (see below)
import time
T0 = time.time()
env = dict(os.environ, PCRECOMP_MUTE='1', MSYS_NO_PATHCONV='1', W2K_FIXED_TICK='12345', W2K_FIXED_TIME='1000000000')   # (sol's and freecell's deals)
# the lifted builds see only a file box of their own (pcrecomp refuses to start one without)
env['PCRECOMP_FILEBOX'] = os.path.join(ROOT, 'work', 'ibox')
# XP's own look, Luna (tools/profile.py luna): its .msstyles as data in the box, from the one
# tools/run_explorer.sh expands from the CD. Stage 1 runs on the host's look, so with Luna its
# column is informational only. XP_LUNA=0: the classic look.
import shutil
LUNA = os.path.join('C', 'WINDOWS', 'Resources', 'Themes', 'Luna', 'luna.msstyles')
_src, _dst = os.path.join(ROOT, 'work', 'profile', LUNA), os.path.join(env['PCRECOMP_FILEBOX'], LUNA)
if os.path.exists(_src) and not os.path.exists(_dst):
    os.makedirs(os.path.dirname(_dst), exist_ok=True); shutil.copyfile(_src, _dst)
LUNA_ON = os.environ.get('XP_LUNA', '1') != '0' and os.path.exists(_dst)
APPROVE, STRICT = '--approve' in sys.argv, '--strict' in sys.argv
ARGS = [a for a in sys.argv[1:] if a not in ('--approve', '--strict')]
def display():   # the session's screen in physical pixels and the DPI the shell applied (AppliedDPI)
    import winreg
    u = ctypes.windll.user32; u.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    try: dpi = winreg.QueryValueEx(winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Control Panel\Desktop\WindowMetrics'), 'AppliedDPI')[0]
    except OSError: dpi = u.GetDpiForSystem()
    return '%dx%d@%d' % (u.GetSystemMetrics(0), u.GetSystemMetrics(1), dpi)
DISP = display()
print('display', DISP)
RUNS = [(app, run, steps) for app in (ARGS or APPS) for run, steps in APPS[app]]
for app, run, steps in RUNS:
    shots = [t for _, t, _ in steps]
    extra = sum((s for _, _, s in steps), [])
    # the box's own Shell Folders/Environment/ProfileList (regbox32 never reads the host's): Windows 2000's
    # C:\Documents and Settings names, registry only (no file box here, so no folders are made)
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'profile.py'), 'xp\\' + app, '-', r'C:\Documents and Settings'],
                   check=True, capture_output=True)
    for build in (app, 'nt' + app):
        if not os.path.exists(os.path.join(ROOT, BUILD, build + '.exe')): continue   # (no stage 1 build: never the original)
        cmd = [sys.executable, os.path.join(ROOT, 'tools', 'hiddenrun.py'), '--secs', str(int(2 * max(shots)) + 4),
               '--settle', '--scale', '2', '--hold', '3' if app in SLOW else '1.5'] + (['--still-crop', '26'] if app == 'sol' else [])   # event-driven: the step times (x2) are only limits
        for t in shots:
            cmd += ['--shot', str(t)]
        cmd += extra + ['--out', os.path.join(ROOT, 'shots', '%s_%s' % (run, build)), '--',
                        os.path.join(ROOT, BUILD, build + '.exe'), '--mute', '--watchdog', str(int(2 * max(shots)) + 2)]   # (after the last shot's limit, 2x, which winmine's ticking clock can use up; before hiddenrun's --secs: a hang leaves its watchdog dump in the log)
        r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        open(os.path.join(ROOT, "shots", "%s_%s.out" % (run, build)), "w").write(r.stdout + r.stderr)   # hiddenrun's timeline, for a missing shot
import hashlib, json, shutil
GDIR, GMAN = os.path.join(ROOT, 'shots', 'golden', DISP), os.path.join(ROOT, 'tools', 'golden.json')
allman = json.load(open(GMAN)) if os.path.exists(GMAN) else {}
man = allman.get(DISP, {})
def crop(I, app):   # sol's status bar "Time:" runs on the host build's own clock (W2K_FIXED_TICK freezes only the lifted one)
    I = I.convert('RGB')
    return I.crop((0, 0, I.size[0], I.size[1] - 26)) if app == 'sol' else I
def ndiff(A, B):
    if A.size != B.size: return 'size %dx%d vs %dx%d' % (A.size + B.size)
    return str(sum(1 for p in ImageChops.difference(A, B).get_flattened_data() if p != (0, 0, 0)))
fails = skips = 0
for app, name, t, run in ((app, n, t, r) for app, r, steps in RUNS for n, t, _ in steps):
    a, b = (os.path.join(ROOT, 'shots', '%s_%s_%d.png' % (run, k, int(t))) for k in (app, 'nt' + app))
    for f in (a, b):
        if os.path.exists(f) and os.path.getmtime(f) < T0: os.remove(f)   # a stale shot is no shot
    if not os.path.exists(b):
        print('%-8s %-13s missing lifted shot' % (app, name)); fails += 1
        continue
    B = crop(Image.open(b), app)
    s1 = ndiff(crop(Image.open(a), app), B) if os.path.exists(a) else 'missing'
    # (no stage 1 build: skipped; mspaint/wordpad's lifted builds load Windows 2000's own comctl32 toolbar, stage 1 the host's: by design)
    if s1 != '0' and app not in S1_DIFFERS and not LUNA_ON and os.path.exists(os.path.join(ROOT, BUILD, app + '.exe')): fails += 1
    key, h = os.path.basename(b), hashlib.sha256(B.tobytes()).hexdigest()
    g = os.path.join(GDIR, key)
    if APPROVE:
        os.makedirs(GDIR, exist_ok=True); shutil.copy(b, g); man[key] = h; gs = 'approved'
    elif not man:
        gs = 'SKIP: no golden for this display'; skips += 1
    elif key not in man:
        gs = 'NO GOLDEN'; fails += 1
    elif man[key] == h:
        gs = '0'
    elif os.path.exists(g) and max(hi for _, hi in ImageChops.difference(crop(Image.open(g), app), B).getextrema()) <= 2:
        gs = '0 (+-2)'   # ponytail: host ClearType drifts by 1 between sessions (stage 1 too); a real change is far more
    else:
        gs = 'FAIL ' + (ndiff(crop(Image.open(g), app), B) if os.path.exists(g) else 'hash') + ' px'; fails += 1
    print('%-8s %-13s %dx%d  stage1 %-8s golden %s' % (app, name, B.size[0], B.size[1], s1, gs))
if APPROVE:
    allman[DISP] = dict(sorted(man.items()))
    json.dump(dict(sorted(allman.items())), open(GMAN, 'w'), indent=1); open(GMAN, 'a').write('\n')
if skips: print('SKIP: no golden for this display (%s; goldens for %s)' % (DISP, ', '.join(allman) or 'none'))
sys.exit(1 if fails or (skips and STRICT) else 0)
