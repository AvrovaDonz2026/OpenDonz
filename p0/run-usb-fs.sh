#!/usr/bin/env bash
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OT_ROOT=${OPENTITAN_ROOT:-/Users/zxy/opentitan}
EXPECTED_OT=2e20836f9c9787bad82c84b5ba704223f06c8890
mkdir -p "$ROOT/p0/logs" "$ROOT/p0/reports"
REPORT="$ROOT/p0/reports/usb-fs-$(date -u +%Y%m%dT%H%M%SZ).txt"
exec > >(tee "$REPORT") 2>&1
printf 'P0 USB Full-Speed candidate check\nUTC: %s\n' "$(date -u +%FT%TZ)"
printf 'Requirement: Full-Speed 12 Mbit/s; High-Speed out of scope\n'
lint_status=2
synth_status=2
mapping_status=2
if ! git -C "$OT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then echo 'BLOCKED: OpenTitan checkout unavailable'; exit 2; fi
ACTUAL_OT=$(git -C "$OT_ROOT" rev-parse HEAD)
printf 'OpenTitan commit: %s\n' "$ACTUAL_OT"
if [[ -n $(git -C "$OT_ROOT" status --porcelain -- hw/ip/usbdev/rtl hw/ip/prim/rtl hw/ip/prim_generic/rtl) ]]; then echo 'BLOCKED: pinned RTL has local modifications'; exit 2; fi
if [[ "$ACTUAL_OT" != "$EXPECTED_OT" ]]; then echo "BLOCKED: expected pinned OpenTitan $EXPECTED_OT"; exit 2; fi
RTL="$OT_ROOT/hw/ip/usbdev/rtl"; PRIM="$OT_ROOT/hw/ip/prim/rtl"; GENERIC="$OT_ROOT/hw/ip/prim_generic/rtl"
FILES=("$RTL/usb_consts_pkg.sv" "$RTL/usb_fs_nb_in_pe.sv" "$RTL/usb_fs_nb_out_pe.sv" "$RTL/usb_fs_rx.sv" "$RTL/usb_fs_tx.sv" "$RTL/usb_fs_tx_mux.sv" "$RTL/usb_fs_nb_pe.sv" "$GENERIC/prim_flop.sv" "$ROOT/p0/src/usb_fs_nb_pe_top.sv")
shasum -a 256 "${FILES[@]}" "$ROOT/p0/lib/"*.combined.lib
for f in "${FILES[@]}" "$PRIM/prim_assert.sv" "$PRIM/prim_flop_macros.sv"; do [[ -f "$f" ]] || { echo "BLOCKED: missing source $f"; exit 2; }; done
for tool in verilator yosys; do if command -v "$tool" >/dev/null 2>&1; then "$tool" --version; else echo "$tool: unavailable"; fi; done
if command -v verilator >/dev/null 2>&1; then
  echo '== Verilator lint/elaboration: usb_fs_nb_pe, 64-byte packet =='
  if verilator --lint-only --timing -Wall -Wno-fatal -DSYNTHESIS -I"$PRIM" --top-module usb_fs_nb_pe_top "${FILES[@]}" >"$ROOT/p0/logs/verilator-usb-fs.log" 2>&1; then echo 'PASS: Verilator elaboration/lint (warnings retained; see log)'; lint_status=0; else echo 'FAIL: Verilator'; lint_status=1; fi
  cat "$ROOT/p0/logs/verilator-usb-fs.log"
else echo 'BLOCKED: Verilator unavailable'; fi
if command -v yosys >/dev/null 2>&1; then
  YOSYS_READ=''
  YOSYS_PLUGIN_ARGS=()
  if [[ -z "${YOSYS_SLANG_PLUGIN:-}" ]]; then
    for candidate in /nix/store/*-yosys-slang/share/yosys/plugins/slang.so; do
      [[ -f "$candidate" ]] && YOSYS_SLANG_PLUGIN="$candidate" && break
    done
  fi
  if [[ -n "${YOSYS_SLANG_PLUGIN:-}" && -f "$YOSYS_SLANG_PLUGIN" ]] && yosys -Q -m "$YOSYS_SLANG_PLUGIN" -p 'help read_slang' >/dev/null 2>&1; then
    YOSYS_READ='read_slang'; YOSYS_PLUGIN_ARGS=(-m "$YOSYS_SLANG_PLUGIN")
    echo "PASS: loaded slang plugin $YOSYS_SLANG_PLUGIN"
  else
    echo 'BLOCKED: slang plugin is unavailable'; echo 'Generic synthesis and mapping skipped.'
  fi
  if [[ -n "$YOSYS_READ" ]]; then
    YOSYS_FILES="$RTL/usb_consts_pkg.sv $RTL/usb_fs_nb_in_pe.sv $RTL/usb_fs_nb_out_pe.sv $RTL/usb_fs_rx.sv $RTL/usb_fs_tx.sv $RTL/usb_fs_tx_mux.sv $RTL/usb_fs_nb_pe.sv $GENERIC/prim_flop.sv $ROOT/p0/src/usb_fs_nb_pe_top.sv"
    YOSYS_FRONTEND="$YOSYS_READ -DSYNTHESIS -DASSERT(__name,__prop)= -I$PRIM -I$RTL $YOSYS_FILES"
    YOSYS_GENERIC="$YOSYS_FRONTEND; hierarchy -top usb_fs_nb_pe_top; synth -top usb_fs_nb_pe_top; stat"
    if yosys "${YOSYS_PLUGIN_ARGS[@]}" -p "$YOSYS_GENERIC" >"$ROOT/p0/logs/yosys-usb-fs.log" 2>&1; then
      echo 'PASS: generic Yosys synthesis (unmapped RTL)'; synth_status=0
      rg -n 'Number of cells|Number of wires|\$_[A-Z]+' "$ROOT/p0/logs/yosys-usb-fs.log"
    else
      echo 'FAIL: Yosys generic synthesis'; synth_status=1
    fi

    LIBROOT="$ROOT/p0/lib/gf180mcu_fd_sc_mcu7t5v0"
    mkdir -p "$ROOT/p0/reports"
    mapping_status=0
    for corner in tt_025C_3v30 ss_125C_3v00; do
      LIB="${LIBROOT}__${corner}.combined.lib"
      NETLIST="$ROOT/p0/reports/usb_fs_nb_pe_${corner}_mapped.v"
      LOG="$ROOT/p0/logs/yosys-gf180-${corner}.log"
      if [[ ! -s "$LIB" ]]; then echo "BLOCKED: missing Liberty $LIB"; mapping_status=2; continue; fi
      echo "== GF180 mapping: $corner =="
      rm -f "$NETLIST" "${NETLIST}.inputs.sha256"
      MAP_CMD="$YOSYS_FRONTEND; read_liberty -lib $LIB; hierarchy -top usb_fs_nb_pe_top; proc; memory; opt; techmap; opt; dfflibmap -liberty $LIB; abc -liberty $LIB -constr $ROOT/p0/sta/abc.constr -D 12000; clean; check -assert; stat -liberty $LIB; write_verilog -noattr $NETLIST"
      if yosys "${YOSYS_PLUGIN_ARGS[@]}" -p "$MAP_CMD" >"$LOG" 2>&1 \
        && python3 "$ROOT/p0/buffer-reset.py" "$NETLIST" \
        && yosys -Q -p "read_liberty -lib $LIB; read_verilog $NETLIST; hierarchy -check -top usb_fs_nb_pe_top; check -assert; stat -liberty $LIB" >"${LOG%.log}-buffered.log" 2>&1 \
        && [[ -s "$NETLIST" ]] \
        && ! rg -q 'Found and reported [1-9][0-9]* problems' "$LOG" \
        && ! rg -q '\$_[A-Za-z0-9_]+|blackbox' "$NETLIST"; then
        shasum -a 256 "${FILES[@]}" "$LIB" "$ROOT/p0/run-usb-fs.sh" "$ROOT/p0/buffer-reset.py" "$ROOT/p0/sta/abc.constr" "$NETLIST" >"${NETLIST}.inputs.sha256"
        echo "PASS: GF180 mapped netlist, non-empty, no unmapped/blackbox cells ($corner)"
        rg -n 'cells|Chip area|problems|Warning: Wire' "${LOG%.log}-buffered.log"
      else
        echo "FAIL: GF180 mapping or netlist verification ($corner)"; mapping_status=1
        rg -n 'ERROR|Number of cells|Chip area|problems|Warning: Wire|unmapped' "$LOG"
      fi
    done
  fi
else echo 'BLOCKED: Yosys unavailable'; synth_status=2; fi
cat <<'END'
== Interpretation ==
This run excludes USB analog PHY, package/PCB, timing constraints, and full usbdev comparison. GF180 mapping uses the locked 7t5v0 Liberty corners documented in dependencies.lock. Generic synthesis is not GF180 area or USB compliance. usb_fs_nb_pe lacks endpoint buffer RAM, TL-UL, and CSR wrapper; full usbdev includes those and a fixed 2 KiB packet SRAM.
END
printf 'RESULT: lint=%s synthesis=%s mapping=%s\n' "$lint_status" "$synth_status" "$mapping_status"
if [[ $lint_status -eq 1 || $synth_status -eq 1 || $mapping_status -eq 1 ]]; then exit 1; fi
if [[ $lint_status -eq 2 || $synth_status -eq 2 || $mapping_status -eq 2 ]]; then exit 2; fi
