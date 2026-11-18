#!/usr/bin/env python3
"""Microsoft's public symbols for a rebased guest module, as "VA name" lines.

    py -3 tools/pdbsyms.py work/rebased-shell/explorer.exe > work/pdb/explorer.syms.txt

The PDB comes from the symbol server by the image's CodeView id (pcrecomp's
tools/pe/pdb_ref.py fetch, cached in work/pdb), its publics are read with
llvm-pdbutil, and a BBT-optimized image's addresses go through the PDB's
OMAP (most XP binaries are). Both stay in the ignored work/.
"""
import bisect, os, re, struct, subprocess, sys, tempfile
import pefile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.environ.get('PCRECOMP', os.path.join(ROOT, '..', 'pcrecomp')), 'tools', 'pe'))
import pdb_ref  # noqa: E402

UTIL = os.environ.get('PDBUTIL', r'C:\Program Files\LLVM\bin\llvm-pdbutil.exe')


def main():
    img = sys.argv[1]
    data = open(img, 'rb').read()
    pe = pefile.PE(data=data, fast_load=True)
    cache = os.path.join(ROOT, 'work', 'pdb')
    pe.parse_data_directories([pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DEBUG']])
    cv = next(d.entry for d in pe.DIRECTORY_ENTRY_DEBUG if d.struct.Type == 2)   # (pdb_ref's codeview_id reads PE32+ only)
    name, key = cv.PdbFileName.rstrip(b'\0').decode(), cv.Signature_String
    path = pdb_ref.fetch(name, key, cache)
    run = lambda *a: subprocess.run([UTIL] + list(a), capture_output=True, text=True).stdout
    streams = run('dump', '--streams', path)
    def stream(label):
        m = re.search(r'Stream\s+(\d+)\s*\(\s*\d+ bytes\): \[%s\]' % re.escape(label), streams)
        if not m:
            return b''
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 's.bin')
            run('export', '--stream=' + m.group(1), '--out=' + out, path)
            return open(out, 'rb').read()
    om = stream('Omap From Source Data')
    om = [struct.unpack_from('<II', om, i) for i in range(0, len(om), 8)]
    src = [a for a, _ in om]
    sh = stream('Section Header Original Data') if om else b''
    secs = ([struct.unpack_from('<I', sh, i * 40 + 12)[0] for i in range(len(sh) // 40)] if sh
            else [s.VirtualAddress for s in pe.sections])
    base = pe.OPTIONAL_HEADER.ImageBase
    out = []
    # S_PUB32 records straight from the symbol record stream (llvm-pdbutil's -publics faults on some)
    rec, p = stream('Symbol Records'), 0
    pubs = []
    while p + 4 <= len(rec):
        n, kind = struct.unpack_from('<HH', rec, p)
        if kind == 0x110E:
            o, s = struct.unpack_from('<IH', rec, p + 8)
            pubs.append((s, o, rec[p + 14:rec.index(b'\0', p + 14)].decode('latin-1')))
        p += n + 2
    for s, o, name in pubs:
        if not 0 < s <= len(secs):
            continue
        rva = secs[s - 1] + o
        if om:
            i = bisect.bisect_right(src, rva) - 1
            if i < 0 or om[i][1] == 0:
                continue
            rva = om[i][1] + rva - om[i][0]
        out.append((base + rva, name))
    for va, n in sorted(out):
        print('%08X %s' % (va, n))


if __name__ == '__main__':
    main()
