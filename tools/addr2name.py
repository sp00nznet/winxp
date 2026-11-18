#!/usr/bin/env python3
"""Nearest export at or below each address, over the rebased guest modules.

    py -3 tools/addr2name.py 2004C2AD 20009B7A
Windows 2000 SP4's .dbg symbols are not on Microsoft's symbol server, so the
export tables are the only names there are.
"""
import bisect, glob, os, sys
import pefile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
mods = []
for f in glob.glob(os.path.join(ROOT, 'work', os.environ.get('W2K_REBASED', 'rebased-shell'), '*.dll')):
    p = pefile.PE(f)
    b = p.OPTIONAL_HEADER.ImageBase
    ex = sorted((b + e.address, e.name.decode()) for e in p.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
    mods.append((b, b + p.OPTIONAL_HEADER.SizeOfImage, os.path.basename(f), ex))
for a in sys.argv[1:]:
    v = int(a.replace('sub_', ''), 16)
    for lo, hi, name, ex in mods:
        if lo <= v < hi:
            i = bisect.bisect_right([e[0] for e in ex], v) - 1
            print('%08X  %s!%s+0x%X' % (v, name, ex[i][1], v - ex[i][0]) if i >= 0 else '%08X %s' % (v, name))
            break
    else:
        print('%08X  ?' % v)
