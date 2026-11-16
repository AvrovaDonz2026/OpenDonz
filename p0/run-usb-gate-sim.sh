#!/usr/bin/env bash
# Zero-delay Liberty functional models, actual mapped cells; no timing simulation claim.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
exec > >(tee "$ROOT/p0/reports/usb-gate-sim-$STAMP.txt") 2>&1
for corner in tt_025C_3v30 ss_125C_3v00; do
  net="$ROOT/p0/reports/usb_fs_nb_pe_${corner}_mapped.v"
  lib="$ROOT/p0/lib/gf180mcu_fd_sc_mcu7t5v0__${corner}.combined.lib"
  build="$ROOT/p0/logs/gate-sim/$corner"
  mkdir -p "$build"
  shasum -a 256 -c "${net}.inputs.sha256"
  shasum -a 256 "$ROOT/p0/dv/usb_pe_test.cpp" "$0"
  yosys -Q -p "read_liberty -ignore_miss_func $lib; write_verilog -noattr $build/cells.v" > "$build/models.log" 2>&1
  verilator --cc --exe --build -j 4 -Wall -Wno-fatal --assert --top-module usb_fs_nb_pe_top --Mdir "$build" "$build/cells.v" "$net" "$ROOT/p0/dv/usb_pe_test.cpp" > "$build/build.log" 2>&1
  for diff in 0 1; do
    for flip in 0 1; do
      for phase in 0 1 2 3; do
        "$build/Vusb_fs_nb_pe_top" "$diff" "$flip" "$phase"
      done
    done
  done
  echo "PASS: $corner 368 directed protocol checks on actual mapped netlist"
done
