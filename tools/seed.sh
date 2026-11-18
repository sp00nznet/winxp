#!/bin/sh
# tools/seed.sh RUN.LOG [DIR]: a run's ICALL/ITAIL misses into work/seeds/<module>.json
# (each lifted module in DIR, default work/rebased-gui), for tools/lift.py's next catalog
D=${2:-work/rebased-shell}
for f in "$D"/*.dll "$D"/*.exe; do
  b=$(basename "$f" | tr A-Z a-z)
  py -3 "${PCRECOMP:-../pcrecomp}/tools/disasm/seed_from_log.py" "$1" "$f" --seeds "work/seeds/$b.json" 2>&1 | grep " + " | sed "s|^|$b: |"
done
