#!/usr/bin/env python3
"""Disassemble a guest module at an export or address (pcrecomp's capstone).

    py -3 tools/disas.py work/rebased/ntdll.dll LdrInitializeThunk [count]
"""
import sys
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

p = pefile.PE(sys.argv[1])
b = p.OPTIONAL_HEADER.ImageBase
img = p.get_memory_mapped_image()
where = sys.argv[2]
ex = {e.name.decode(): b + e.address for e in p.DIRECTORY_ENTRY_EXPORT.symbols if e.name} if hasattr(p, 'DIRECTORY_ENTRY_EXPORT') else {}
va = ex[where] if where in ex else int(where, 16)
n = int(sys.argv[3]) if len(sys.argv) > 3 else 30
for i, ins in enumerate(Cs(CS_ARCH_X86, CS_MODE_32).disasm(img[va - b:va - b + 16 * n], va)):
    if i >= n:
        break
    print('%08X  %-8s %s' % (ins.address, ins.mnemonic, ins.op_str))
