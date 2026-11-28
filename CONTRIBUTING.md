# Contributing

Issues and pull requests are welcome.

## The one rule

**Nothing from Windows goes in the repository.** No CD image and no files
from it (expanded or rebased, `luna.msstyles` and `Bliss.bmp` included), no
lifted C (`src/gen/`), no catalogs, symbols (`work/pdb`) or other analysis
output (`work/`, apart from the address-only seeds in `work/seeds`), no
disassembly listings, nothing generated from XP's binaries. The tool ships;
its output is made on each person's machine from their own copy.
`.gitignore` covers the usual paths; check `git status` before you commit
anyway. Screenshots of Windows running are fine.

## Where your code comes from

Write it yourself, from XP's own behavior, Microsoft's documentation and
pcrecomp. Don't bring in code from GPL or LGPL projects (Wine, ReactOS,
DOSBox) or from other emulators, and don't write code with them open.
Permissively licensed code is fine with its notice kept: add a `NOTICE` row
(path, upstream, version, license) and its license text under `LICENSES/`.

## Before a pull request

1. Build from a clean lift: `Setup.cmd -Force`, or the README's "Building by
   hand".
2. Run the checks:
   ```
   py -3 tools/interact.py
   sh tools/run_explorer.sh check 30
   ```
   `interact.py` must match the approved goldens for your display (the
   states with known gaps have none yet); `run_explorer.sh` fails when any
   host module other than advapi32 is mapped into the guest. A new behavior
   comes with a state or a check that shows it.
3. A change to the shared runtime in pcrecomp is checked on
   [win2000](https://github.com/sp00nznet/win2000) too: win2000 built against
   the changed toolkit must match its own build in `interact.py`, row for
   row.
4. A wall you got past goes in `docs/survey.md`'s handoff: what it looked
   like, what it was, what moved it.

## Where a fix belongs

- A bug in the lifter or the runtime belongs in
  [pcrecomp](https://github.com/sp00nznet/pcrecomp), not here; an answer
  only XP needs goes behind the guest's build number
  (`runtime/native32/ntguest.h`), so Windows 2000 keeps working.
- A fix to how XP is hosted, lifted or set up goes in `src/`, `tools/` or
  `CMakeLists.txt`, with a comment that says what it fixes and why.
