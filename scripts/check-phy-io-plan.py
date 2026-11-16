#!/usr/bin/env python3
"""Validate proposed pin reservations against existing RTL/slot, without EDA tools."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def check(condition, message):
    if not condition:
        raise SystemExit("FAIL: " + message)


def main():
    plan = json.loads((ROOT / "docs/phy-io-pinout.json").read_text())
    check(plan["schema_version"] == 1, "unsupported schema")
    check(plan["status"] == "proposal-not-package-pinout", "proposal status missing")
    check(plan["slot"] == "0p5x0p5", "checker supports quarter slot only")
    defines = (ROOT / "src/slot_defines.svh").read_text().split(
        "`ifdef SLOT_0P5X0P5", 1)[1].split("`endif", 1)[0]
    counts = {name: int(value) for name, value in re.findall(
        r"`define NUM_(\w+)_PADS\s+(\d+)", defines)}
    check(counts == dict(DVDD=3, DVSS=3, VDD=1, VSS=1, INPUT=4,
                         BIDIR=38, ANALOG=4), "slot resource boundary changed")
    slot = (ROOT / "librelane/slots/slot_0p5x0p5.yaml").read_text()
    # Slot strings quote and escape bracketed generated instance names.
    instances = re.findall(r"(?:clk_pad|rst_n_pad|(?:bidir|inputs|analog|"
                           r"dvdd_pads|dvss_pads|vdd_pads|vss_pads)"
                           r"\[\d+\]\.pad)", slot.replace("\\", ""))
    check(len(instances) == 56 and len(set(instances)) == 56,
          "expected 48 signal plus 8 unique power pads")
    for group, count in plan["power_pad_instances"].items():
        check(count == counts[group.removesuffix("_pads").upper()],
              "power count differs: " + group)
        for index in range(count):
            check(f"{group}[{index}].pad" in instances, "missing power pad")
    check(set(plan["power_pad_instances"]) ==
          {"dvdd_pads", "dvss_pads", "vdd_pads", "vss_pads"}, "power groups changed")
    for mode, pins in plan["modes"].items():
        seen_pads, seen_signals = set(), set()
        for pin in plan["common"] + pins:
            pad, signal = pin["pad"], pin["signal"]
            check(pad not in seen_pads, mode + ": duplicate pad " + pad)
            check(signal not in seen_signals, mode + ": duplicate signal " + signal)
            seen_pads.add(pad)
            seen_signals.add(signal)
            check(pin["direction"] in {"input", "output", "inout"}, "bad direction")
            if pad in {"clk_PAD", "rst_n_PAD"}:
                instance = {"clk_PAD": "clk_pad", "rst_n_PAD": "rst_n_pad"}[pad]
            else:
                match = re.fullmatch(r"(input|bidir|analog)_PAD\[(\d+)\]", pad)
                check(match is not None, "unknown pad " + pad)
                kind, index = match.group(1), int(match.group(2))
                check(index < counts[kind.upper()], "pad index out of range")
                group = "inputs" if kind == "input" else kind
                instance = f"{group}[{index}].pad"
            check(instance in instances, "pad missing from slot: " + instance)
        print(f"PASS: {mode}: {len(seen_pads)} distinct candidate signal pads")
    pe = (ROOT / "p0/src/usb_fs_nb_pe_top.sv").read_text().split(");", 1)[0]
    ports = set(re.findall(r"(?:input|output)\s+logic\s*(?:\[[^\]]+\]\s*)?"
                           r"(\w+)", pe))
    check(set(plan["required_pe_ports"]) <= ports, "required PE port missing")
    doc = ROOT / "docs/phy-io-plan.md"
    for target in re.findall(r"\]\(([^)]+)\)", doc.read_text()):
        if not target.startswith(("https://", "http://", "#")):
            check((doc.parent / target.split("#", 1)[0]).exists(), "broken link " + target)
    lock = dict(line.split("=", 1) for line in
                (ROOT / "p0/dependencies.lock").read_text().splitlines()
                if line and not line.startswith("#"))
    for corner in ("tt_025C_3v30", "ss_125C_3v00"):
        lib = ROOT / "p0/lib" / f"gf180mcu_fd_sc_mcu7t5v0__{corner}.combined.lib"
        if lib.exists():
            check(hashlib.sha256(lib.read_bytes()).hexdigest() ==
                  lock[f"gf180_scl_{corner}_sha256"], "Liberty hash mismatch")
            print("PASS: local standard-cell Liberty " + corner)
        else:
            print("UNAVAILABLE: optional generated standard-cell Liberty " + corner)
    print(f"PASS: proposal references actual slot resources and {len(ports)} PE ports; "
          "this does not validate PHY electrical behavior or package bonding")


if __name__ == "__main__":
    main()
