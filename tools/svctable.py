#!/usr/bin/env python3
"""The NT service table from an ntdll's own export stubs, both stub forms
(Windows 2000's int 2Eh, XP SP2+'s call through KUSER_SHARED_DATA).

    py -3 tools/svctable.py work/sys/ntdll.dll [other/ntdll.dll]

One file: "0xNNN Name argc" lines. Two: the services whose number moved.
"""
import sys
import pefile


def table(path):
    p = pefile.PE(path)
    out = {}
    for e in p.DIRECTORY_ENTRY_EXPORT.symbols:
        if not e.name or not e.name.startswith(b'Nt'):
            continue
        b = p.get_data(e.address, 16)
        if b[0] != 0xB8:
            continue
        if b[5:11] == bytes.fromhex('8d542404cd2e'):
            r = 11
        elif b[5:12] == bytes.fromhex('ba0003fe7fff12'):
            r = 12
        else:
            continue
        argc = int.from_bytes(b[r + 1:r + 3], 'little') // 4 if b[r] == 0xC2 else 0
        out[e.name.decode()] = (int.from_bytes(b[1:5], 'little'), argc)
    return out


if __name__ == '__main__':
    a = table(sys.argv[1])
    if len(sys.argv) == 2:
        for n, (s, c) in sorted(a.items(), key=lambda kv: kv[1]):
            print('0x%03X %s %d' % (s, n, c))
    else:
        b = table(sys.argv[2])
        same = sum(1 for n in a if n in b and a[n] == b[n])
        print('%d services in %s, %d in %s; %d same number, %d only in the first, %d only in the second'
              % (len(a), sys.argv[1], len(b), sys.argv[2], same, len(set(a) - set(b)), len(set(b) - set(a))))
        print('only in the first:', ' '.join(sorted(set(a) - set(b))))
