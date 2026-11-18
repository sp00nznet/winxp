#!/usr/bin/env python3
"""Run an accessory twice, on the host's gdi32 (stage 1) and on Windows 2000's
own lifted gdi32 (build/gdi<app>.exe), and compare the windows pixel by pixel.

    py -3 tools/gdicmp.py sol [--secs 7] [-- args]
Shots in shots/cmp_<app>_host.png, shots/cmp_<app>_gdi.png, the difference in
shots/cmp_<app>_diff.png. Runs on hiddenrun's private desktop, muted.
"""
import os, subprocess, sys
import ctypes
ctypes.windll.kernel32.SetErrorMode(0x8003)   # no loader/fault box on the real desktop (inherited)
from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = sys.argv[1]
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
secs = float(sys.argv[sys.argv.index('--secs') + 1]) if '--secs' in sys.argv else 7
os.environ['PCRECOMP_MUTE'] = '1'
os.environ['PCRECOMP_FILEBOX'] = os.path.join(ROOT, 'work', 'ibox')   # (pcrecomp refuses a lifted ntdll without one)
os.environ['MSYS_NO_PATHCONV'] = '1'
os.environ['W2K_FIXED_TIME'] = '1000000000'   # the same deal in both runs (sol)
shots = {}
for kind, exe in (('host', app + '.exe'), ('gdi', 'ntwmgdi.exe' if app == 'winmine' else 'gdi' + app + '.exe')):
    out = os.path.join(ROOT, 'shots', 'cmp_%s_%s' % (app, kind))
    cmd = [sys.executable, os.path.join(ROOT, 'tools', 'hiddenrun.py'), '--secs', str(secs + 2), '--shot', str(secs),
           '--out', out, '--', os.path.join(ROOT, 'build', exe), '--mute', '--watchdog', str(int(secs + 1))]
    if args:
        cmd += ['--'] + args
    subprocess.run(cmd, cwd=ROOT, capture_output=True)
    png = '%s_%d.png' % (out, int(secs))
    if not os.path.exists(png):
        sys.exit('%s: no window (see %s.log)' % (kind, out))
    os.replace(png, out + '.png')
    shots[kind] = Image.open(out + '.png').convert('RGB')
a, b = shots['host'], shots['gdi']
if a.size != b.size:
    print('%s: sizes differ: host %s, gdi %s' % (app, a.size, b.size))
    sys.exit(1)
d = ImageChops.difference(a, b)
n = sum(1 for p in d.get_flattened_data() if p != (0, 0, 0)) if hasattr(d, 'get_flattened_data') else sum(1 for p in d.getdata() if p != (0, 0, 0))
d.point(lambda v: 255 if v else 0).save(os.path.join(ROOT, 'shots', 'cmp_%s_diff.png' % app))
print('%s: %dx%d, %d pixels differ%s' % (app, a.size[0], a.size[1], n, '' if not n else ' in %s' % (d.getbbox(),)))
