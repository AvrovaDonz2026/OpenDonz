# Isolated OpenTitan crypto assessment

Authoritative analysis: ../docs/opentitan-crypto-assessment.md. OpenTitan is the preferred production path; MbedTLS remains reference/development only.

Pinned upstream: `/Users/zxy/opentitan`, HEAD `2e20836f9c9787bad82c84b5ba704223f06c8890`. No upstream tracked source edits. Local paths intentionally describe this reproducibility environment.

## Commands

- `.venv/bin/python vectors.py`: build unmodified upstream P-256 vector entrypoints and run ISA model expectations and stats (not RTL).
- `.venv/bin/python independent_check.py`: compare resulting key/signature against Python cryptography/OpenSSL.
- `.venv/bin/python assess.py hmac --map`: full HMAC RTL closure export + GF180 mapping.
- `.venv/bin/python assess.py otbn --macros --map`: full OTBN RTL closure, real SRAM blackboxes, mandatory 59 macro count assertion, GF180 logic mapping. Allow several minutes for ABC.
- `/nix/store/s2g847svsh7lf0gkz0n1z1y6bq3lk95v-opensta/bin/sta -exit build/hmac/timing.tcl`: ideal-clock pre-layout STA (not signoff).
- Same STA tool with `build/otbn/timing.tcl`: includes SRAM Liberty; three clocks assumed equal for initial diagnostic only. Actual CDC, reset/false-path and multicycle constraints must be derived from integration; do not treat diagnostic constraints as signoff.

SRAM functional tests use Verilator --binary --timing -Wno-fatal, top macro_tb, upstream prim_ram_1p_pkg.sv, pinned SRAM .v, rtl/prim_ram_1p.sv, rtl/macro_tb.sv. Default parameters test IMEM 4096x39; `-GWidth=312 -GDepth=1024` tests DMEM. Build each parameter set in a separate --Mdir. Testbench requires per-bank read priming to meet model CEN initialization. Logs in build/macro-test.log and build/dmem-test.log. Verilator does not make this a complete specify/SDF signoff test.

## Build caveats

FuseSoC local installed schema allowed empty file lists (minItems 0); upstream contains an empty waiver list. Python dependencies are isolated in .venv. Assembler architecture override is rv32i_zicsr. Slang needs --single-unit and prelude includes. Critically, Slang needs --empty-blackboxes: its default expansion of an empty SRAM module discards macros and creates undriven outputs. First invalid log saved as build/otbn/invalid-no-blackbox.log; its 4.196781 mm² is NOT a valid OTBN area.

Input file/Liberty hashes: build/{otbn,hmac}/inputs.json. Upstream software/tool/vector hashes and license inventories: evidence/. Real macro sizing and incomplete platform work are documented in the report. Do not assume EDN/OTP/keymgr/KMAC providers are included merely because packages are in the closure. Never modify shared SoC or PHY files for this experiment.

## Isolated 8 KiB IMEM evaluation

Run from the repository root with `crypto-hw/.venv/bin/python`:

1. `crypto-hw/configure.py`: copy pinned upstream OTBN into ignored build/imem8, change only IMEM window to 2048 words, regenerate register RTL/C header using upstream reggen. Tool memory views/linker derive from the copied HJSON. Default upstream and baseline stay unchanged.
2. `crypto-hw/full_p256.py`: assemble/link complete official run_p256 and execute all eleven mode values plus changed-message/invalid-mode tests. Python cryptography independently checks selected arithmetic/signatures. This is ISA execution with synthetic randomness and initial wipe bypassed, NOT RTL/security signoff.
3. `crypto-hw/boundaries.py`: exact/overflow capacity, fetch bounds and invalid DMEM/instruction ISA errors.
4. `crypto-hw/rtl_tests.py`: SHA256 abc KAT/digest wipe; 2048x39 IMEM and 1024x312 DMEM macro adapters using real pinned models. Builds archives explicitly to avoid Darwin sandbox xargs issue.
5. `crypto-hw/driver_check.py`: official dif_hmac.c host compile and mocked-MMIO contract; generated device-tree types are host-only adapters, no hardware digest proof.
6. `crypto-hw/assess.py otbn --imem8 --macros --map`: isolated full-IP synthesis, 49-macro assertions before and after mapping. `effective-inputs.json` hashes actual overlay/replacement sources.
7. `crypto-hw/sta.py otbn8`: diagnostic pre-layout STA, same baseline constraints and SRAM Liberty. Also accepts otbn/hmac.
8. `crypto-hw/audit_sram.py`: use cached pinned 512x8 views, fetching missing views only; emit area/organization manifest. Platform acceptance/GDS qualification remains external.

Full OTBN top RTL simulation requires upstream Verilator >=5.048; installed 5.046 can execute the small primitive/macro tests but does not satisfy that top target. No entropy, ECC, scrambling, wipe, or reseeding logic is disabled in synthesized OTBN. The ISA harness alone bypasses startup wipe and supplies synthetic random values. Do not claim production security from these tests.
