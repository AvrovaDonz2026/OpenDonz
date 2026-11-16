# P0: reproducible USB Full-Speed candidate check

This P0 artifact compares upstream OpenTitan blocks for a CanoKey-style USB HID transport requiring USB Full-Speed (12 Mbit/s). It does **not** implement a PHY, claim USB compliance, or promise a complete security-key design.

Current accepted result: **TT/SS 48 MHz pre-layout STA pass**, with final mapped
areas **39853.8560 / 42090.7648 µm²**. See [RESULTS.md](RESULTS.md) for the
compact retained evidence and limits. Earlier numbers below are historical.

## Source-verified scope

- OpenTitan `usbdev` calls itself a **USB Full Speed Device Interface** (`hw/ip/usbdev/rtl/usbdev.sv`); its packet engine is also explicitly Full-Speed. USB 2.0-compatible Full-Speed is not High-Speed (480 Mbit/s). High-Speed is out of scope.
- The full `usbdev` top fixes `SramDepth=512`, a 32-bit SRAM word, and 64-byte packets: 2 KiB packet RAM plus TL-UL/CSR, endpoint FIFOs, registers, and interrupt logic. Reducing depth requires checking dependent FIFO/address/register logic.
- `usb_fs_nb_pe` is the upstream non-buffered Full-Speed protocol engine (RX/TX and IN/OUT engines), without packet RAM/TL-UL/CSR. It is a low-cost candidate only with a small custom endpoint/HID control wrapper. Its 32-byte default packet parameter is configurable; this check uses 64 bytes.
- Both options still need external/custom analog PHY and board circuitry. RTL synthesis area does not include pads/PHY/electrical cost.

## Revisions

- OpenTitan commit `2e20836f9c9787bad82c84b5ba704223f06c8890` (`p0/dependencies.lock`). The runner checks this revision and will stop on mismatch.
- Exact toolchain inputs are recorded in root `flake.lock`; relevant source revisions are summarized in `dependencies.lock`.
- OpenTitan source is consumed in place, not vendored or modified.

## Run

From project root, prepare external dependencies once (Git/network access required):

```sh
git clone --filter=blob:none --no-checkout https://github.com/lowRISC/opentitan.git ../opentitan
git -C ../opentitan checkout --detach 2e20836f9c9787bad82c84b5ba704223f06c8890
export OPENTITAN_ROOT="$(cd ../opentitan && pwd)"
python3 p0/prepare-dependencies.py
```

Use an existing checkout instead of cloning if available; it must have the locked
revision and clean relevant RTL. The Liberty helper fetches into ignored
`p0/.cache/`, assembles the official header plus sorted per-cell Liberty blocks,
and verifies both SHA256 values in `dependencies.lock` before writing either
input. `--gf180-source PATH` uses an existing clean pinned GF180 checkout. Existing
different Liberty inputs are never overwritten. Generated Liberty, reports,
netlists, and builds remain local; they are not required in the Git archive.

Enter the pinned tools and run:

```sh
nix develop --no-write-lock-file --accept-flake-config --command ./p0/run-usb-fs.sh
```

The runner checks the pinned upstream revision and a clean relevant RTL tree, records source/Liberty SHA256 fingerprints and tool versions, and runs Verilator lint, Yosys/slang generic synthesis and GF180 TT/SS mapping. It discovers the separate Nix `slang.so` package and loads its absolute path with `yosys -m`. Synthesis disables upstream assertion macros; simulation enables assertions. Missing dependencies are blocked, never counted as passes. Reports are timestamped in `p0/reports/`; detailed stage logs are in `p0/logs/`.

## GF180 7t5v0 technology mapping

The runner also maps the standalone `usb_fs_nb_pe_top` candidate through the official
`gf180mcu_fd_sc_mcu7t5v0` standard-cell Liberty at two representative 3.3 V corners:
`tt_025C_3v30` and `ss_125C_3v00`. The project-local files under `p0/lib/` are assembled
from the official per-cell Liberty files at commit
`43beb45e4d323a76239de436db2df6732e9a689b`; the source is Apache-2.0 licensed and the
license is retained as `p0/lib/GF180-LICENSE`. Hashes, units, voltage and corner names are
in `p0/dependencies.lock`. This is an isolated dependency, not a global PDK install.

Historical 13:33 mapping (superseded by the final closure below):

The flow imports Liberty models before mapping and runs `dfflibmap`, `abc -liberty`, `clean`, `check -assert`, and `stat -liberty`, then writes a gate-level Verilog netlist. The 2026-11-15 rerun (`reports/usb-fs-20261115T133323Z.txt`) passes lint, generic synthesis and both mappings: **1,073 cells and 33,961.9392 µm² (0.033962 mm²)** at each corner, with zero check problems and no unmapped/blackbox cells.

### Corrected wrapper boundary

The old 629-cell / 19,313.3696 µm² result was reproducible but was not a credible active PE baseline: the wrapper tied `link_active_i=0` and hid endpoint interfaces, allowing synthesis to prune active transaction logic. The wrapper now exposes the complete PE boundary (2 IN + 2 OUT endpoints, 64-byte packets), including active-link controls, endpoint data/handshake interfaces, toggles and error outputs. Functional simulation and synthesis use this same top. The old area must not be used for budgeting the functioning PE.

This is standard-cell area before placement; PHY, HID/EP0 control, TL-UL/CSR, endpoint RAM, pads, package, PDN, clock-tree/hold repair and routing are excluded. Pre-layout STA is a separate run described below; it does not replace extracted physical STA.

### Undriven-output warning investigation

The earlier four mapped-netlist warnings were caused by the verification sequence, not by
unconnected RTL outputs. Generic synthesis reported `Found and reported 0 problems`. Each
warning named one of the four registered TX outputs (`u_oe_flop.q_o`,
`u_usb_se0_o_flop.q_o`, `u_usb_dp_o_flop.q_o`, `u_usb_dn_o_flop.q_o`); the upstream
`usb_fs_tx.sv` explicitly connects each `prim_flop.q_o` to its corresponding output.
The mapped netlist also contained each Q on a GF180 `dffrnq_1` or `dffsnq_1` instance with
its D, clock, and reset/preset connections.

The diagnostic was reproduced as a Yosys model-import issue: mapping with `dfflibmap` and
`abc -liberty` but without first importing the Liberty cells caused `check` to see the
mapped cell Q pins as undriven. The GF180 Liberty model itself has complete `ff(IQ1,IQN1)`
state declarations and Q pins; it is not a missing Q/QN model. The mapping command now runs
`read_liberty -lib` before hierarchy and mapping. Both TT and SS reruns report `Found and
reported 0 problems`, and the runner treats any nonzero final `check` count as mapping
failure. The original warnings and their resolution remain in the timestamped logs.

## Digital protocol regression

```sh
nix develop --no-write-lock-file --accept-flake-config --command ./p0/run-usb-sim.sh
```

`dv/usb_pe_test.cpp` is a lightweight independent deterministic host codec, not the full OpenTitan UVM/usbdpi environment. It drives DP/DN NRZI with bit stuffing, independently computes token CRC5 and payload CRC16, decodes actual device TX, and checks packet bytes, handshakes, commit/rollback and toggle behavior. The runner sweeps differential/single-ended RX, pin flip, and four 48 MHz sampling phases (16 configurations). Each configuration checks:

- Asynchronous reset, idle, link reset and toggle clearing.
- IN empty NAK, wrong address/endpoint silence, IN STALL.
- Valid/invalid SOF CRC5 and frame index validity.
- OUT DATA0 with stuffing/CRC16/ACK/toggle; duplicate OUT rollback; CRC5/CRC16, PID complement and bit-stuff errors.
- Full OUT NAK and STALL with rollback; EP0 SETUP ACK and DATA1 initialization.
- Serialized IN payload/stuffing/CRC16, host ACK commit, DATA1 and missing-ACK timeout/rollback.
- Zero-length and 64-byte IN/OUT, including OUT address saturation at 63.

The earlier run `reports/usb-sim-20261115T133437Z.txt` passed all 16 configurations (23 directed checks each, 368 total).

The PE streams **both trailing CRC16 bytes** through `out_ep_data_put_o`, including on zero-length packets. Its address saturates at 63, and stops advancing when the transaction is being NAKed. A future endpoint wrapper must discard the CRC tail and commit only on ACK; direct writes into a 64-byte buffer can overwrite its last payload byte with CRC. The first scoreboard assumed payload-only data and failed; it was corrected against the upstream PE/usbif contract, without modifying upstream RTL. Failed exploratory reports remain in the archive.

This is directed digital verification, not USB/HID compliance certification. Enumeration, descriptors, CTAPHID/U2F, suspend/resume, isochronous endpoints, clock jitter/frequency tolerance, exhaustive malformed packets, CDC/metastability, gate-level timing and analog pad/PHY electrical behavior are not covered. No product GO follows from these tests alone.

## 48 MHz pre-layout STA closure — 2026-11-15 14:58 UTC

Final local result: `reports/sta-20261115T145829Z.txt`, exit **0**.
The checked-in summary is [RESULTS.md](RESULTS.md); timestamped reports and
input snapshots cited here are ignored local artifacts, regenerated by the runners.
Mapping/lint: `reports/usb-fs-20261115T145826Z.txt`; RTL regression:
`reports/usb-sim-20261115T145829Z.txt` (368 checks / 16 configurations).
Exact sources, netlists, SDC and checker are archived with SHA256 manifests in
`sta-{corner}-20261115T145829Z-inputs/`. Earlier results are historical.

Unchanged budget: 20.833333 ns, setup/hold uncertainty 0.5/0.1 ns, I/O max/min
3.0/0.5 ns, transition 0.2 ns, output load 0.05 pF. Synchronous control/endpoint
ports remain constrained; usb_d_i/usb_dp_i/usb_dn_i remain asynchronous and
unconstrained. No timing cuts, false paths, multicycles or removed reset checks.

- TT: setup WNS **+7.2861 ns**, TNS **0 ns**, min slack **+0.2564 ns**;
  minimum recovery **+16.4347 ns**, removal **+1.0944 ns**.
- SS: setup WNS **+1.6943 ns**, TNS **0 ns**, min slack **+0.1489 ns**;
  minimum recovery **+15.2428 ns**, removal **+1.7222 ns**.
- Integrated baseline: TT +6.5481 / 0 / −0.1273 ns WNS/TNS/min;
  SS −1.3025 / −20.7696 / −0.5930 ns.
- Final mapped area including buffers: TT **1348 cells / 39853.8560 µm²**;
  SS **1348 cells / 42090.7648 µm²**, versus baseline 1344 cells and
  36528.1280/36993.5104 µm² (area +9.10%/+13.78%).

### Implementation

`run-usb-fs.sh` tightens ABC's target from 18000 to 12000 ps, retaining buf_4
input drive and 50 fF load. `buffer-reset.py` upgrades all 246 pin-compatible
GF180 dffrnq/dffsnq drive-1 flops to drive 4. ABC does not resize sequential
launch cells; this improves Q slew/fanout on RX endp_q → IN endpoint-index and
handshake cones without modifying upstream protocol RTL or adding latency.
Drive repair alone left SS WNS −0.4484 ns; tighter ABC mapping closed it.

Two rising-edge reset-release stages and asynchronous assertion remain. Internal
reset distribution retains 4 buf_8 roots / 31 buf_4 leaves for 244 RN/SETN sinks.
Four real GF180 buf_1 cells delay external rst_ni to both synchronizer RN pins.
External minimum arrival is now 1.7472 ns TT / 2.8924 ns SS, versus removal
required 0.6528/1.1702 ns. External recovery is +16.4347/+15.6206 ns; SS global
recovery minimum +15.2428 ns is internal. Global min slack is normal data hold.

This is valid **only under the existing 0.5–3 ns after-clock reset release
contract** and these two corners. A fixed delay cannot make arbitrary-phase
asynchronous release safe: it can shift a transition into a forbidden window.
Arbitrary-phase release qualification remains open if required; no first-stage
check is waived. Assertion acquires actual buffer delay; minimum reset pulse
width, fast corners, metastability, CTS/skew, routed RC and preservation of the
inserted cells need physical verification. Wait until the third rising edge
after compliant release before protocol traffic/writes. This is cell-delay
pre-layout closure, not extracted signoff, USB compliance or overall P0 GO.

### Verification

Lint, generic synthesis, GF180 TT/SS mapping, hierarchy/check assertions, all 368
RTL protocol checks, and complete two-corner STA pass. `test-sta-gate.py` now
exposes the three asynchronous USB pins required by the coverage checker and
verifies real pass=0 and actual reset-removal failure=1 at both corners.

`run-usb-gate-sim.sh` additionally runs the same 368 checks per corner on the
actual final mapped netlists using zero-delay Liberty functional models. Both
corners passed in `reports/usb-gate-sim-20261115T150001Z.txt`; this is not
SDF timing simulation. Model import ignores missing functions on unused ICG
cells; actual instantiated cells are elaborated and functionally exercised.
Build warnings are retained in `p0/logs/gate-sim/`.

After dependency preparation, enter the pinned Nix shell and run sequentially:

```sh
nix develop --no-write-lock-file --accept-flake-config
./p0/run-usb-fs.sh
./p0/run-usb-sim.sh
./p0/run-usb-sta.sh
python3 p0/test-sta-gate.py
bash p0/run-usb-gate-sim.sh
```

Source/provenance hashes are checked; real timing failure remains exit 1 and
missing/tool/coverage failure exit 2. No commit or deployment was made.
