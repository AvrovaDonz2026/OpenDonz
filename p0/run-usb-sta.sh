#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
P0="$ROOT/p0"
STA_DIR="$P0/sta"
mkdir -p "$P0/logs" "$P0/reports"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
REPORT="$P0/reports/sta-$STAMP.txt"
exec > >(tee "$REPORT") 2>&1
printf 'P0 USB PE pre-layout OpenSTA run\nUTC: %s\n' "$(date -u +%FT%TZ)"
printf 'Target: usb_fs_nb_pe_top; 2 IN + 2 OUT endpoints; MaxPktSizeByte=64\n'
printf 'Clock target: 48 MHz, period 20.833333 ns\n'
if ! command -v sta >/dev/null 2>&1; then
  echo 'BLOCKED: OpenSTA executable "sta" is unavailable; enter the pinned Nix shell.'
  exit 2
fi
sta -version 2>&1 || true
RTL_TOP="$P0/src/usb_fs_nb_pe_top.sv"
if [[ ! -s "$RTL_TOP" ]]; then
  echo "BLOCKED: updated pass-through wrapper is missing: $RTL_TOP"
  exit 2
fi
# Guard against the old shell that tied link_active_i low and hid PE endpoints.
REQUIRED_PORTS=(
  clk_i rst_ni link_reset_i link_active_i dev_addr_i cfg_eop_single_bit_i
  cfg_use_diff_rcvr_i cfg_pinflip_i tx_osc_test_mode_i out_data_toggle_o
  out_datatog_we_i out_datatog_status_i out_datatog_mask_i in_data_toggle_o
  in_datatog_we_i in_datatog_status_i in_datatog_mask_i diff_rx_ok_i
  out_ep_current_o out_ep_data_put_o out_ep_put_addr_o out_ep_data_o
  out_ep_newpkt_o out_ep_acked_o out_ep_rollback_o out_ep_setup_o
  out_ep_enabled_i out_ep_control_i out_ep_full_i out_ep_stall_i out_ep_iso_i
  in_xact_starting_o in_xact_start_ep_o in_ep_current_o in_ep_rollback_o
  in_ep_xact_end_o in_ep_get_addr_o in_ep_data_get_o in_ep_newpkt_o
  in_ep_enabled_i in_ep_stall_i in_ep_has_data_i in_ep_data_done_i in_ep_iso_i
  sof_detected_o sof_valid_o frame_index_o rx_idle_det_o rx_j_det_o
  rx_crc5_err_o rx_crc16_err_o rx_pid_err_o rx_bitstuff_err_o usb_d_i usb_dp_i
  usb_dn_i usb_d_o usb_se0_o usb_dp_o usb_dn_o usb_oe_o event_datatog_out_o
  event_timeout_in_o event_nak_in_o event_nodata_in_o in_ep_data_i
)
check_ports() {
  local file=$1
  python3 - "$file" "${REQUIRED_PORTS[@]}" <<'PYPORTS'
import re, sys
path, *required = sys.argv[1:]
text = open(path, encoding="utf-8").read()
match = re.search(r"\bmodule\s+usb_fs_nb_pe_top\s*\((.*?)\)\s*;", text, re.S)
if not match:
    print(f"BLOCKED: {path} has no parseable usb_fs_nb_pe_top port declaration")
    raise SystemExit(1)
header = match.group(1)
missing = [name for name in required if not re.search(rf"\b{re.escape(name)}\b", header)]
if missing:
    print(f"BLOCKED: {path} top-level port list is incomplete: {', '.join(missing)}")
    raise SystemExit(1)
PYPORTS
}
if ! check_ports "$RTL_TOP"; then
  echo 'STA not run: waiting for the main-agent wrapper update.'
  exit 2
fi
LIBROOT="$P0/lib/gf180mcu_fd_sc_mcu7t5v0"
STATUS=0
for CORNER in tt_025C_3v30 ss_125C_3v00; do
  case "$CORNER" in
    tt_025C_3v30) NETLIST="$P0/reports/usb_fs_nb_pe_tt_025C_3v30_mapped.v" ;;
    ss_125C_3v00) NETLIST="$P0/reports/usb_fs_nb_pe_ss_125C_3v00_mapped.v" ;;
  esac
  LIB="${LIBROOT}__${CORNER}.combined.lib"
  LOG="$P0/logs/sta-$CORNER-$STAMP.log"
  PREFIX="$P0/reports/sta-$CORNER-$STAMP"
  if [[ ! -s "$NETLIST" ]]; then
    echo "BLOCKED: mapped netlist not available: $NETLIST"
    STATUS=2
    continue
  fi
  if ! check_ports "$NETLIST"; then
    echo "STA not run for $CORNER: mapped netlist is stale/incomplete."
    STATUS=2
    continue
  fi
  if [[ ! -s "$LIB" ]]; then
    echo "BLOCKED: Liberty not available: $LIB"
    STATUS=2
    continue
  fi
  if [[ ! -s "${NETLIST}.inputs.sha256" ]] || ! shasum -a 256 -c "${NETLIST}.inputs.sha256" >"${PREFIX}-provenance.rpt" 2>&1; then
    echo "BLOCKED: mapped inputs changed or provenance missing for $CORNER"
    STATUS=2
    continue
  fi
  echo "== OpenSTA $CORNER =="
  export STA_TOP=usb_fs_nb_pe_top STA_CORNER="$CORNER" STA_LIB="$LIB"
  export STA_NETLIST="$NETLIST" STA_SDC="$STA_DIR/usb-fs-pe.sdc" STA_PREFIX="$PREFIX"
  mkdir -p "${PREFIX}-inputs"
  cp "$STA_DIR/usb-fs-pe.sdc" "${PREFIX}-inputs/design.sdc"
  cp "$STA_DIR/run.tcl" "$STA_DIR/check-results.py" "$0" "${PREFIX}-inputs/"
  shasum -a 256 "$RTL_TOP" "$NETLIST" "$LIB" "$STA_DIR/usb-fs-pe.sdc" "$STA_DIR/run.tcl" "$STA_DIR/check-results.py" >"${PREFIX}-inputs/sha256.txt"
  cp "$NETLIST" "${PREFIX}-inputs/mapped.v"
  cp "$RTL_TOP" "$P0/run-usb-fs.sh" "$P0/buffer-reset.py" "$STA_DIR/abc.constr" "${PREFIX}-inputs/"
  cp "${NETLIST}.inputs.sha256" "${PREFIX}-inputs/mapping-inputs.sha256"
  cp "$P0/dv/usb_pe_test.cpp" "$P0/run-usb-sim.sh" "${PREFIX}-inputs/"
  export STA_NETLIST="${PREFIX}-inputs/mapped.v" STA_SDC="${PREFIX}-inputs/design.sdc"
  if sta -no_splash -exit "${PREFIX}-inputs/run.tcl" >"$LOG" 2>&1; then
    if python3 "$STA_DIR/check-results.py" "$PREFIX" "$LOG"; then
      echo "PASS: $CORNER"
    else
      rc=$?
      echo "FAIL: $CORNER status=$rc"
      if [[ $rc -gt $STATUS ]]; then STATUS=$rc; fi
    fi
  else
    echo "FAIL: OpenSTA exited nonzero for $CORNER; see $LOG"
    STATUS=2
  fi
  cat "$LOG"
done
echo '48 MHz strict original budget: 0.5/0.1 ns uncertainty; 3/0.5 ns I/O; 0.2 ns transition; 0.05 pF load.'
echo 'Synchronous controls/endpoint ports constrained; usb_d_i/usb_dp_i/usb_dn_i asynchronous and unconstrained; no timing cuts.'
echo 'Reset recovery/removal checks remain enabled; review reset and unconstrained reports.'
echo 'Ideal clock, no RC/CTS: pre-layout feasibility only.'
printf 'RESULT: status=%s report=%s\n' "$STATUS" "$REPORT"
exit "$STATUS"
