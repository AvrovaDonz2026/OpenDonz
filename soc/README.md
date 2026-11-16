# GF180 measurement boundary

`soc_boundary_top` places Ibex and the P0 two-endpoint protocol engine side by side.
It exposes CPU memory transactions, USB endpoint controls and debug request externally.
It does **not** implement an executable SoC, mailbox bridge, USB enumeration, memory
macro wrapper, RNG, timer, storage controller or debug interconnect.

## Reproduce

Use the repository Nix environment (`nix develop --no-write-lock-file`) for Yosys,
OpenROAD and Verilator. Current Yosys is 0.69; slang must be installed/enabled.

```sh
python3 -m pip install --target soc/.tools -r soc/requirements.txt
export OPENTITAN=/path/to/locked/opentitan # defaults to sibling ../opentitan
# Must be commit 2e20836f9c9787bad82c84b5ba704223f06c8890.
# FuseSoC 2.4.6 upstream empty waiver workaround described below.
PYTHONPATH=soc/.tools:firmware/.tools python3 soc/measure.py ibex --export
PYTHONPATH=soc/.tools:firmware/.tools python3 soc/measure.py usbdev --export
PYTHONPATH=soc/.tools:firmware/.tools python3 soc/measure.py debug
PYTHONPATH=soc/.tools:firmware/.tools python3 soc/measure.py dtm
PYTHONPATH=soc/.tools:firmware/.tools python3 soc/measure.py rom
PYTHONPATH=soc/.tools:firmware/.tools python3 soc/measure.py boundary
PYTHONPATH=soc/.tools python3 soc/report.py
```

Set `YOSYS` / `SLANG_PLUGIN` for nondefault executables/plugin paths. On this machine
SLANG_PLUGIN was `/nix/store/*-yosys-slang/share/yosys/plugins/slang.so` expanded to
the single installed plugin. The `.core` backend arch field is only a FuseSoC export
requirement; `measure.py` performs GF180 mapping itself, not Xilinx synthesis.

The installed FuseSoC schema rejects empty upstream waiver filesets. For this locked
version, change `"minItems": 1` to `"minItems": 0` in
`soc/.tools/fusesoc/capi2/json_schema.py` before exporting. This only relaxes list
validation; no upstream RTL or protected repository source must be patched.
`--ignore-initial` bypasses unsupported initialization constructs; assertions are
excluded for synthesis. This is a measurement concession, not functional proof.

Source manifests hash every elaboration file and the reused P0 TT 3.3V Liberty.
OpenTitan/lowRISC are Apache-2.0 (retain file-specific notices); the debug module
retains PULP Solderpad 0.51 notices. SRAM LEF source:
https://github.com/RTimothyEdwards/gf180mcu_ocd_ip_sram/tree/d41c7447d34d0c298158094378c8268560941724
Only geometric evidence is included; no macro timing/GDS integration or fabrication
license qualification is implied. Per-file notices remain in the retrieved LEF.

No full PDK technology LEF / compatible macro Liberty+GDS installation was found.
OpenROAD is installed, but a routed SoC floorplan cannot be truthfully produced from
Liberty and SRAM dimensions alone. `capacity.json` is an arithmetic capacity screen.

## Executable development integrations

`soc_firmware_top` now connects actual Ibex to generated ROM, inferred 16 KiB
RAM and MMIO mailbox/timer/button. `soc_boundary_top` above remains the older
measurement boundary and is not this executable integration.
`soc_usb_top` additionally connects the existing two-endpoint PE through
`usb_u2f_bridge` for hardware EP0 plus 64-byte HID mailbox traffic.

```sh
PYTHONPATH=soc/.tools:firmware/.tools python3 soc/test_firmware.py
PYTHONPATH=soc/.tools:firmware/.tools python3 soc/test_usb.py
```
The USB regression drives digital D+/D- and decodes independent CRC/NRZI,
checks descriptors/address/configuration, actual firmware INIT/VERSION, retries,
CRC rejection, duplicate suppression, stall recovery and explicit link reset.
This is not physical-host USB qualification. The top has a **nonpersistent NVM
stub** (erased reads, writes acknowledged/discarded), external test entropy,
inactive button, disabled debug, no attach/VBUS/reset detector and unassigned
VID/PID. No registration/authentication/persistence is claimed. New integration
logic has not yet been mapped or included in the capacity totals.

OpenTitan OTBN P-256 + OT HMAC is the preferred crypto route; Mbed TLS is only
a qualified temporary reference/development backend. Integration awaits the
independent `crypto-hw/` interface/dependency assessment, with no speculative OT
driver stub. Do not reject OpenTitan from unmapped generic SRAM flop area or
force capabilities to fit quarter slot. Final combined measurements are pending.

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

Evidence text whitespace is normalized for Git review. The SRAM LEF has only
trailing blank lines removed; its capacity SHA256 records the retained file.
