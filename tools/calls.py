#!/usr/bin/env python3
"""Name a --calltrace file's entries that are exports of the guest modules.

    py -3 tools/calls.py shots/calls.txt [FROM_EXPORT] [N]
Prints the exported functions entered, in order, starting at the last entry
of FROM_EXPORT (default: the start), N of them (default 200).
"""
import glob, os, sys
import pefile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ex = {}
for f in glob.glob(os.path.join(ROOT, 'work', os.environ.get('W2K_REBASED', 'rebased'), '*.dll')) + glob.glob(os.path.join(ROOT, 'work', os.environ.get('W2K_REBASED', 'rebased'), '*.exe')):
    p = pefile.PE(f)
    b = p.OPTIONAL_HEADER.ImageBase
    tag = os.path.basename(f).split('.')[0] + '!'
    for e in (p.DIRECTORY_ENTRY_EXPORT.symbols if hasattr(p, 'DIRECTORY_ENTRY_EXPORT') else []):
        if e.name:
            ex.setdefault(b + e.address, tag + e.name.decode())
names = [ex.get(int(l.split()[1], 16)) for l in open(sys.argv[1]) if len(l.split()) > 1]
start = 0
if len(sys.argv) > 2:
    hits = [k for k, n in enumerate(names) if n and n.endswith('!' + sys.argv[2])]
    start = hits[-1] if hits else 0
n = int(sys.argv[3]) if len(sys.argv) > 3 else 200
print(' '.join([x for x in names[start:] if x][:n]))
