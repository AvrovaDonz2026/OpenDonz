# RV32 U2F checkpoint

This is a buildable port and measurement fixture, not a complete USB U2F device.
See `../docs/checkpoint1-soc-u2f-assessment.md` for measured results and blockers.

## Crypto implementation priority

**OpenTitan OTBN P-256 and OT HMAC are the preferred implementation route;
production architecture is not frozen.** The independent assessment owns
`crypto-hw/` and `docs/opentitan-crypto-assessment.md`. Integration awaits its
verified interfaces/dependencies; no unverified OT driver stub is implemented here.
`ecc_compute_public_p256r1` / `ecdsa_sign_p256r1` remain replaceable port interfaces;
HMAC/SHA must be adapted to the OT contract when available. Mbed TLS is solely the
qualified reference model and temporary development backend. Its existing PASS
qualification is retained; it does not select the production architecture or
establish side-channel/security/performance properties for the final OT combination.
OpenTitan capabilities will not be discarded to force quarter-slot fit, and
unmapped generic SRAM-to-flop area does not disqualify OpenTitan.

## Rebuild

```sh
python3 firmware/bootstrap.py
python3 -m pip install --target firmware/.tools -r firmware/requirements-test.txt
# Clang with RISC-V backend, LLD, llvm-size and llvm-readelf required.
# Put LLVM tools on PATH; CC, HOST_CC, LD, LLVM_SIZE and LLVM_READELF override defaults.
python3 firmware/build.py
python3 firmware/test_rv32.py
# Crypto qualification: 14 boundary cases, RFC 6979 public vector, signature cross-check and entropy failures.
python3 firmware/test_crypto_edges.py
```

The build uses RV32IMC/ilp32, freestanding `-Oz`, strict compiler warnings,
`-fstack-usage`, a 16 KiB RAM map and a 4 KiB stack reservation. Artifacts are in
`build/`; reviewable evidence snapshots are in `evidence/`. `stack.json` records individual frames, not a proven call-chain bound.
The emulator uses deterministic test entropy. Never use that entropy in a device.
P-256 uses Mbed TLS 3.6.5 commit `e185d7fd85499c8ce5ca2a54f5cf8fe7dbe3f8df` (Apache-2.0 or GPL-2.0-or-later), built with a minimal freestanding configuration and an 8 KiB zeroized static arena. Qualification passes 14 scalar cases, the RFC 6979 public-key vector, independently verified signatures and four entropy failure cases on native and RV32. This is functional qualification, not side-channel signoff. Mbed TLS scalar multiplication has countermeasures, but this port has not undergone timing/cache/physical side-channel assessment. Hardware RNG readiness failures bubble up as operation errors; entropy quality and health tests are not established. The former micro-ecc failure remains archived under `evidence/history/micro-ecc/`.
`test_rv32.py` is an instruction-emulator smoke test. A separate Verilator test runs Ibex reset/startup and HID INIT/U2F_VERSION through the mailbox; The separate `soc/test_usb.py` regression exercises digital USB D+/D- descriptor/address/configuration and actual firmware INIT/VERSION. Persistent NVM and full registration/authentication are not integrated.

## Source and license lock

* gl-sergei/u2f-token commit `2c19a75c31096e19cbcfcedeae6bb18077eabac0`:
  https://github.com/gl-sergei/u2f-token/tree/2c19a75c31096e19cbcfcedeae6bb18077eabac0
  APDU/HID/HMAC code GPL-3.0-or-later, with upstream section-7 permission.
  SHA-256 retains Brian Gladman's license notice (permissive conditions / GPL alternative).
* Historical failed implementation: kmackay/micro-ecc commit `541b3a78026420a3e369c4c9281c396b5e531113`:
  https://github.com/kmackay/micro-ecc/tree/541b3a78026420a3e369c4c9281c396b5e531113
  BSD-2-Clause, copyright Kenneth MacKay. Portable C, no P-256 hardware engine.

Upstream README records deployment on STM32/Tomu devices; this is evidence of an
existing U2F implementation, not independent assurance of correctness or this port.
Bootstrap retains upstream source/license files. Distribution of the combined firmware
must satisfy the GPL and all retained notices. `inputs.json` hashes compiled sources,
headers, curve include files and port/linker/certificate inputs.

* Mbed TLS 3.6.5 commit `e185d7fd85499c8ce5ca2a54f5cf8fe7dbe3f8df`, Apache-2.0 or GPL-2.0-or-later.

## Port contract (BASE = 0x40000000)

All registers are 32-bit little endian. Matching mailbox RTL is exercised by the current RTL smoke test; the development USB endpoint/EP0 bridge is exercised separately by `soc/test_usb.py`.

* +0x00 status: bit0 RX-ready, bit1 TX-ready; +0x04 RX byte pop;
  +0x08 TX byte push; +0x0c packet strobes 1 RX release / 2 TX commit.
  Transfer unit is one 64-byte HID report. The development bridge provides EP0 descriptors/address/configuration; this is not real-host/PHY enumeration.
* +0x10 button: read bit0 presence; write 1 clears hardware latch. Software also latches.
* +0x18 wrapping **microsecond** timer; upstream timeout 500000 means 500 ms.
* +0x20 RNG ready bit0; +0x24 consumes one entropy byte. Unready returns an error (fail closed).
  Health tests, conditioner, entropy quality and nonblocking retry policy are absent.
* +0x30 NVM address; +0x38 write byte; +0x34 command/status:
  1 erase 1 KiB page / busy bit0, 4 write byte / busy bit2, error bit1.
  Read mapping at 0x20000000 must expose erased 0xff and coherent completed writes.
  Controller semantics are a proposed contract, not verified persistence.
* +0x3c must equal 0x55324631 before main starts.

`chopstx_create` runs the only HID loop synchronously on the main stack. It is not
an RTOS port; the upstream process-stack argument is ignored. No heap is linked.
`port/cert/certificates.c` deliberately leaves attestation unprovisioned (0xffffffff).
Device key/counter/attestation reserve 1 KiB each in NVM, not SRAM.

## Reference resource snapshot and RTL reproduction

The software reference ELF has `.text` 24,084 B, `.data` 12 B and `.bss` 9,748 B:
9,760 B static RAM (plus 4 B linker alignment). The 16 KiB RAM and 4 KiB stack
reservation are budgets, not proven minimum requirements. Written-stack lower
bounds are 696 B (public key), 792 B (signature), 40 B (VERSION); static frames
and written watermarks are different measurements. The 8 KiB crypto arena is
static storage with internal allocator use, not a system heap.

After the locked source exports/ROM generation described in soc/README:
```sh
PYTHONPATH=soc/.tools:firmware/.tools python3 soc/test_firmware.py
PYTHONPATH=soc/.tools:firmware/.tools python3 soc/test_usb.py
PYTHONPATH=soc/.tools:firmware/.tools python3 soc/report.py
```
`soc_usb_top` is a **development test integration**: external link-reset input,
no pullup/VBUS/reset detector, unassigned 0000 VID/PID, external entropy driven
by deterministic test bytes, button tied inactive, debug disabled, and a
**NONPERSISTENT NVM STUB** (erased reads, acknowledged/discarded writes).
It must not be used for actual keys or described as complete registration/authentication.
EP0 currently supports the tested small descriptors/control requests only; no
string descriptors, full malformed-request qualification, suspend/resume or
endpoint halt management. Final OT integration requires fresh resource/security/performance measurements.

## Evidence provenance and portability

Evidence is a retained measurement snapshot, not a claim that every local build
artifact is versioned. Absolute `/Users/zxy/OpenDonz` paths in manifests, stack
frames and size output identify the original measurement workspace; relocate
that prefix to the new checkout when checking hashes. `/nix/store` command paths
and compiler installation paths record the measured tool environment, not a
required installation location. Use PATH and documented environment overrides
for rebuilding; tool versions may change ELF bytes and require new ROM mapping.
The firmware `crypto-upstream.json` and `history/micro-ecc/` describe the former
failed backend only, not current Mbed TLS qualification. Historical FAIL remains
FAIL. Public scalar/nonce values in qualification evidence are synthetic or
published RFC vectors, never device credentials. No attestation private key is
provisioned. Vendor source, Python dependencies and generated builds are ignored.

Rebuild prerequisites: Python 3.12+ for bootstrap tar extraction filtering; the
locked OpenTitan checkout, firmware bootstrap exports, P0 locked Liberty setup
(`p0/README.md`), LLVM/LLD and Nix Verilator/Yosys/slang. Install requirements
from each scope before exporting. `soc/measure.py rom` generates the ROM and
maps it; the other measurement targets plus `soc/report.py` rebuild resource
snapshots. The report copies current build outputs: rerun execution/crypto tests
first when replacing those snapshots. Existing mapped-area snapshots remain
pre-layout measurements; the new USB bridge is still unmeasured.
