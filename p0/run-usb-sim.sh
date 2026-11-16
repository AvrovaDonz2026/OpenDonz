#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OT_ROOT=${OPENTITAN_ROOT:-/Users/zxy/opentitan}
[[ $(git -C "$OT_ROOT" rev-parse HEAD) == 2e20836f9c9787bad82c84b5ba704223f06c8890 ]]
mkdir -p "$ROOT/p0/logs" "$ROOT/p0/reports" "$ROOT/p0/sim_build"
exec > >(tee "$ROOT/p0/reports/usb-sim-$(date -u +%Y%m%dT%H%M%SZ).txt") 2>&1
printf "UTC: %s\n" "$(date -u +%FT%TZ)"
[[ -z $(git -C "$OT_ROOT" status --porcelain -- hw/ip/usbdev/rtl hw/ip/prim/rtl hw/ip/prim_generic/rtl) ]]
shasum -a 256 "$ROOT/p0/src/usb_fs_nb_pe_top.sv" "$ROOT/p0/dv/usb_pe_test.cpp" "$ROOT/p0/run-usb-sim.sh"
verilator --version
RTL="$OT_ROOT/hw/ip/usbdev/rtl"
verilator --cc --exe --build -j 4 -Wall -Wno-fatal --assert -I"$OT_ROOT/hw/ip/prim/rtl" --top-module usb_fs_nb_pe_top --Mdir "$ROOT/p0/sim_build" \
 "$RTL/usb_consts_pkg.sv" "$RTL/usb_fs_nb_in_pe.sv" "$RTL/usb_fs_nb_out_pe.sv" "$RTL/usb_fs_rx.sv" "$RTL/usb_fs_tx.sv" "$RTL/usb_fs_tx_mux.sv" "$RTL/usb_fs_nb_pe.sv" "$OT_ROOT/hw/ip/prim_generic/rtl/prim_flop.sv" "$ROOT/p0/src/usb_fs_nb_pe_top.sv" "$ROOT/p0/dv/usb_pe_test.cpp" > "$ROOT/p0/logs/verilator-usb-sim-build.log" 2>&1
for diff in 0 1; do
  for flip in 0 1; do
    for phase in 0 1 2 3; do
      "$ROOT/p0/sim_build/Vusb_fs_nb_pe_top" "$diff" "$flip" "$phase"
    done
  done
done
