#!/bin/sh
# Show the lifted C around a host address from a fault report:  tools/faultline.sh 0x62C02104 [exe]
exe=${2:-build/cmd.exe}
loc=$("/c/Program Files/LLVM/bin/llvm-symbolizer.exe" --obj="$exe" "$1" | sed -n 2p)
f=${loc%:*}; f=${f%:*}; n=${loc%:*}; n=${n##*:}
echo "$loc"
sed -n "$((n - 30)),$((n + 3))p" "$f" | grep -v "_flag_\|_cf = \|_flag_k"
