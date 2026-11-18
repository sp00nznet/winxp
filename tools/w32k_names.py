#!/usr/bin/env python3
"""win32k service names for one Windows build, as "0xNNNN Name" lines.

    py -3 tools/w32k_names.py "Windows 2000" SP4 > work/names/win32k_2000sp4.txt

From j00ru's public syscall tables (github.com/j00ru/windows-syscalls,
x86/json/win32k-per-system.json, fetched into work/names/). The numbers are
the guest's own: its user32/gdi32 stubs carry them; this only names them.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(ROOT, 'work', 'names', 'win32k-per-system.json')))[sys.argv[1]][sys.argv[2]]
for name, num in sorted(d.items(), key=lambda kv: kv[1]):
    print('0x%04X %s' % (num, name))
