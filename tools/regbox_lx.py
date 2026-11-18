#!/usr/bin/env python3
"""The Linux registry box (pcrecomp ntposix.c ntp_regbox) from a Windows box.

    reg export HKCU\\Software\\pcrecomp\\w2k\\explorer box.reg
    py -3 tools/regbox_lx.py box.reg work/lx/explorer.box

The Windows box (reginst.py's COM classes, profile.py's shell folders and
colours) is HKCU\\Software\\pcrecomp\\w2k\\<app>\\{HKLM,HKCU}; the Linux one is a
text file of full NT key paths with every value as hex(T). Paths in string
values move to the Linux guest's layout: the lifted modules and the host's
System32 become C:\\WINNT\\system32. A value naming any other host drive, and
Explorer's UserAssist (the host's own launches), are left out.
"""
import re, sys

USER = r'\REGISTRY\USER\S-1-5-21-1-2-3-1000'
SYS = [(re.compile(r'[A-Z]:\\(?:[^\\:"]+\\)*?work\\rebased-shell', re.I), r'C:\\WINNT\\system32'),
       (re.compile(r'C:\\Windows\\System32', re.I), r'C:\\WINNT\\system32'),
       (re.compile(r'C:\\Windows\b', re.I), r'C:\\WINNT')]
OTHER = re.compile(r'\b[ABD-Z]:\\', re.I)


def rewrite(s):
    for r, t in SYS:
        s = r.sub(t, s)
    return s


def unq(s):
    return re.sub(r'\\(.)', r'\1', s)


def main(src, dst):
    text = open(src, 'rb').read().decode('utf-16')
    text = re.sub(r'\\\r?\n\s*', '', text)                 # hex continuation lines
    out, key, nk, nv = [], None, 0, 0
    for l in text.splitlines():
        if l.startswith('['):
            m = re.match(r'\[HKEY_CURRENT_USER\\Software\\pcrecomp\\w2k\\[^\\\]]+\\(HKLM|HKCU)(\\.*)?\]$', l)
            key = None
            if m and 'UserAssist' not in l:
                key = (r'\Registry\Machine' if m.group(1) == 'HKLM' else USER) + (m.group(2) or '')
                out.append('[%s]' % key)
                nk += 1
            continue
        if key is None or not l or l[0] not in '"@':
            continue
        m = re.match(r'(@|"((?:[^"\\]|\\.)*)")=(.*)$', l)
        if not m:
            continue
        name = '' if m.group(1) == '@' else unq(m.group(2))
        v = m.group(3)
        if v.startswith('"'):
            t, data = 1, (unq(v[1:-1]) + '\0').encode('utf-16-le')
        elif v.startswith('dword:'):
            t, data = 4, int(v[6:], 16).to_bytes(4, 'little')
        else:
            m2 = re.match(r'hex(?:\(([0-9a-f]+)\))?:(.*)$', v)
            if not m2:
                continue
            t = int(m2.group(1) or '3', 16)
            data = bytes(int(b, 16) for b in m2.group(2).split(',') if b.strip())
        if t in (1, 2, 7):
            s = rewrite(data.decode('utf-16-le', 'replace'))   # (moved first: the lifted modules are on G:)
            if OTHER.search(s):
                continue
            data = s.encode('utf-16-le')
        out.append('%s=hex(%x):%s' % ('@' if not name else '"%s"' % name.replace('\\', '\\\\').replace('"', '\\"'),
                                      t, ','.join('%02x' % b for b in data)))
        nv += 1
    open(dst, 'w', newline='\n').write('\n'.join(out) + '\n')
    print('%s: %d keys, %d values' % (dst, nk, nv))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
