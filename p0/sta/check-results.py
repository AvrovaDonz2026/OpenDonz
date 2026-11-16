#!/usr/bin/env python3
"""Validate OpenSTA reports while allowing only the documented async pins."""
import math
import re
import sys
from pathlib import Path

prefix, log = map(Path, sys.argv[1:])
try:
    log_text = log.read_text()
    if re.search(r"^(?:Error|Warning):", log_text, re.M):
        raise ValueError("OpenSTA emitted an error or warning")

    coverage = Path(str(prefix) + "-check_timing.rpt").read_text().strip()
    expected = "\n".join((
        "Warning: There are 3 input ports missing set_input_delay.",
        "  usb_d_i",
        "  usb_dn_i",
        "  usb_dp_i",
    ))
    if coverage != expected:
        raise ValueError("unexpected check_timing coverage: " + (coverage or "clean"))

    for port in ("usb_d_i", "usb_dp_i", "usb_dn_i"):
        usb = Path(str(prefix) + "-" + port + ".rpt").read_text()
        if not re.search(r"^Startpoint: " + re.escape(port) + r" \(input port\)", usb, re.M):
            raise ValueError("USB asynchronous pin has no reported path: " + port)
        if "Path is unconstrained" not in usb:
            raise ValueError("USB path is unexpectedly constrained: " + port)

    metrics = Path(str(prefix) + "-slack.rpt").read_text()
    values = []
    for name in ("SETUP", "MIN"):
        found = re.findall(r"^P0_" + name + r"_SLACK (\S+)$", metrics, re.M)
        if len(found) != 1 or not math.isfinite(float(found[0])):
            raise ValueError("missing/nonfinite/duplicate " + name)
        values.append(float(found[0]))
    tns = re.findall(r"^tns max ([-+0-9.eE]+)$", metrics, re.M)
    if len(tns) != 1 or not math.isfinite(float(tns[0])):
        raise ValueError("missing/nonfinite TNS")

    violations = Path(str(prefix) + "-violations.rpt").read_text()
    print(metrics, end="")
    failed = any(v < 0 for v in values) or float(tns[0]) < 0 or bool(
        re.search(r"(?:\(VIOLATED\)|^\S+\s+-[0-9])", violations, re.M)
    )
    print("TIMING FAIL" if failed else "TIMING PASS")
    sys.exit(1 if failed else 0)
except (OSError, ValueError) as exc:
    print("BLOCKED:", exc)
    sys.exit(2)
