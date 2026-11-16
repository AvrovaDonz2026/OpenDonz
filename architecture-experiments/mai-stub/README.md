# Official OTBN FeatStubMai knockout experiment

Isolated comparison of OTBN8 with `FeatStubMai=0` versus `FeatStubMai=1`.
Both runs share a frozen source/include snapshot. No crypto-hw or SoC source is
modified. Upstream OpenTitan revision: 2e20836f9c9787bad82c84b5ba704223f06c8890.

Reproduce from repository root with crypto-hw/.venv/bin/python:

- `architecture-experiments/mai-stub/experiment.py prepare`
- `architecture-experiments/mai-stub/experiment.py baseline`
- `architecture-experiments/mai-stub/experiment.py stub`
- `architecture-experiments/mai-stub/experiment.py timing baseline`
- `architecture-experiments/mai-stub/experiment.py timing stub`
- `architecture-experiments/mai-stub/p256_check.py`
- `architecture-experiments/mai-stub/summarize.py`

Generated snapshots, synthesis netlists/logs and ISA binaries stay ignored.
`manifest.json` records exact source hashes. A new prepare replaces snapshots;
finish both runs before preparing another comparison.

Memory: 8 KiB IMEM + 32 KiB physical DMEM (16 KiB bus-visible, remaining
allocation is upstream isolation), including ECC. Both elaborations assert 49
OCD 1024x8 macros before mapping; a postmapping assertion checks retention.
LEF size 301.300 x 515.810 um => 7.615264097 mm2 for all 49 macros.
This is macro geometric area, not physical placement or routing area.

This paired synthesis is specifically **8 KiB IMEM + 32 KiB DMEM with 49
1024x8 macros**, not the previously committed 16 KiB DMEM configuration.
The 13.0854675882 mm2 system lower bound applies only to this measured
32 KiB DMEM configuration. **16 KiB DMEM + FeatStubMai=1 has not been
synthesized**; subtracting memory area or transferring this logic saving does
not constitute a measured or verified result for that combination.

FeatStubMai is an official parameter (default false) in otbn.sv and otbn_core.sv.
It removes the MAI and its masked accelerator. MAI reads return zero; writes to
MAI input/result WSRs or its control CSR raise MAI software error. Programs that
use these operations (e.g. masked symmetric operations) are unsupported. This
experiment keeps all other security parameters at their original values:
ECC, PRINCE memory scrambling, secure wipe, RND/URND and P-256 masking/blinding.
Retaining mechanisms is not a certification of equivalent side-channel security.

The P-256 check copies the current full_p256.py harness into this isolated folder
and runs the full linked run_p256 program across all official entrypoint modes,
plus changed-digest and invalid-mode cases. Its static audit decodes every text
word with the official decoder and rejects MAI WSR 10..15 / CSR 0x7e0 and 0xfca.
The simulation is the upstream ISA model with synthetic entropy and startup wipe
bypassed by its standalone harness; it is not RTL execution of FeatStubMai=1.
No silicon entropy, fault injection, leakage or secure-wipe RTL proof is claimed.

STA reuses the baseline diagnostic clock/IO recipe and actual macro Liberty.
It has ideal clocks and no routed parasitics: results are diagnostic, not signoff.

The frozen prim_ram_1p.sv differs from the historical baseline manifest because
another worker updated the reset behavior and 512-depth support. Hence the new
paired baseline is the authoritative parameter-only comparison; historical
4.268281024 mm2 is reported separately, not presumed identical.

Full slot budget uses the current core 5.020056 mm2. SoC raw area includes OTBN
cells, 7.615264097 mm2 OTBN macros, HMAC 0.931858 mm2 and prior base SoC
0.855116 mm2, and excludes additional system RAM, interconnect/integration,
entropy/NVM/power/clock and placement/routing margin. Exceeding this lower bound
is sufficient to reject fitting; a value below it would not prove fit.

## Measured outcome

Paired baseline cells: 4.270851603199 mm2; MAI-stub cells: 3.683229491200 mm2.
Saving: 0.587622111999 mm2 (13.7588979%). Historical baseline was
4.268281024 mm2; new paired baseline differs by +0.002570579199 mm2.
SRAM macros remain 49 and 7.615264097 mm2. Stub OTBN raw total is
11.2984935882 mm2. Adding prior HMAC/base SoC gives a lower bound of
13.0854675882 mm2, exceeding the 5.020056 mm2 core by 8.0654115882 mm2,
before system SRAM, missing integration logic or any physical margin.
Even the stub logic plus HMAC/base SoC alone is 5.4702034912 mm2,
already 0.4501474912 mm2 over core before any memory.

All 13 full-program ISA checks passed (11 official modes plus altered digest
and invalid mode). Complete linked text: 6260 bytes / 1565 instructions;
zero MAI CSR/WSR accesses. See p256-results.json.

Diagnostic ideal-clock STA core minimum period: baseline 312.46 ns, stub 308.43 ns; fmax 3.2 / 3.24 MHz. No timing improvement is established; neither meets the 24 MHz diagnostic target.

## Archived evidence

`evidence.json` retains small final synthesis/STA excerpts and SHA-256 hashes
of the raw logs, scripts and ELF. Large raw logs, netlists, snapshots and binaries
are deliberately excluded. `manifest.json` records the measured frozen closure;
reproduction requires the pinned toolchain and matching source inputs. Local
absolute paths in scripts/manifests reflect the original measurement machine.
