#!/usr/bin/env python3
"""Repair mapped sequential drive and reset distribution with real GF180 cells."""
import re
import sys
from pathlib import Path
p = Path(sys.argv[1])
s = p.read_text()
# ABC maps combinational cones, but dfflibmap leaves every sequential Q at
# drive 1. Use pin-compatible drive 4 flops to drive the actual mapped cones.
s, resized = re.subn(r"(__dff(?:rnq|snq))_1(?=\s)", r"\g<1>_4", s)
print(f"Sequential drive repair: {resized} flops resized to drive 4")
# Current integration contract permits release 0.5..3 ns after an edge.
# A real four-buffer delay satisfies library removal at both characterized
# corners; recovery remains checked against the next edge. This is NOT a
# guarantee for arbitrary asynchronous release phase or extracted routing.
s, external = re.subn(r"\.RN\(rst_ni\)", ".RN(reset_external_3)", s)
if external != 2:
    raise SystemExit(f"Expected 2 external reset synchronizer sinks, got {external}")
pattern = r"\.(RN|SETN)\(\\dut\.rst_ni \)"
n = len(re.findall(pattern, s))
if n != 244:
    raise SystemExit(f"Expected 244 internal reset sinks, got {n}")
i = 0
def sink(m):
    global i
    group = i // 8
    i += 1
    return f".{m.group(1)}(reset_leaf_{group})"
s = re.sub(pattern, sink, s)
count = (n + 7) // 8
cells = []
for stage in range(4):
    source = "rst_ni" if stage == 0 else f"reset_external_{stage-1}"
    cells += [f"  wire reset_external_{stage};", f"  gf180mcu_fd_sc_mcu7t5v0__buf_1 reset_external_buf_{stage} (.I({source}), .Z(reset_external_{stage}));"]
for root in range((count + 7) // 8):
    cells += [f"  wire reset_root_{root};", f"  gf180mcu_fd_sc_mcu7t5v0__buf_8 reset_root_buf_{root} (.I(\\dut.rst_ni ), .Z(reset_root_{root}));"]
for leaf in range(count):
    cells += [f"  wire reset_leaf_{leaf};", f"  gf180mcu_fd_sc_mcu7t5v0__buf_4 reset_leaf_buf_{leaf} (.I(reset_root_{leaf // 8}), .Z(reset_leaf_{leaf}));"]
s = s.replace("endmodule", "\n".join(cells) + "\nendmodule")
p.write_text(s)
print(f"Reset tree: {n} sinks, {count} leaf buffers, {(count+7)//8} root buffers")
