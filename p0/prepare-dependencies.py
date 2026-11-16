#!/usr/bin/env python3
"""Rebuild the locked GF180 Liberty inputs without vendoring the PDK."""
import argparse
import hashlib
from pathlib import Path
import subprocess

P0 = Path(__file__).resolve().parent
LOCK = dict(line.split("=", 1) for line in (P0 / "dependencies.lock").read_text().splitlines()
            if line and not line.startswith("#"))


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gf180-source", type=Path, help="existing clean pinned GF180 checkout")
    args = parser.parse_args()
    source = args.gf180_source or P0 / ".cache" / "gf180-source"
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout",
                        LOCK["gf180_scl_repo"], str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "checkout", "--detach",
                        LOCK["gf180_scl_commit"]], check=True)
    if git(source, "rev-parse", "HEAD") != LOCK["gf180_scl_commit"]:
        raise SystemExit("BLOCKED: GF180 revision differs from dependencies.lock")
    if git(source, "status", "--porcelain", "--untracked-files=all", "--", "liberty", "cells"):
        raise SystemExit("BLOCKED: GF180 Liberty source has local changes")
    # Match the original assembly byte-for-byte: library header, sorted cells,
    # then the closing library brace. Verify both before writing either output.
    outputs = []
    for corner in ("tt_025C_3v30", "ss_125C_3v00"):
        name = f"gf180mcu_fd_sc_mcu7t5v0__{corner}"
        header = (source / "liberty" / f"{name}.lib").read_text()
        cut = header.rfind("\n}")
        if cut < 0:
            raise SystemExit("BLOCKED: invalid library header")
        cells = []
        for path in sorted((source / "cells").rglob(f"*__{corner}.lib")):
            text = path.read_text()
            start = text.find("  cell(")
            if start >= 0:
                cells.append(text[start:])
        data = (header[:cut] + "\n" + "\n".join(cells) + "\n}\n").encode()
        digest = hashlib.sha256(data).hexdigest()
        if digest != LOCK[f"gf180_scl_{corner}_sha256"]:
            raise SystemExit(f"BLOCKED: assembled {corner} SHA256 mismatch: {digest}")
        outputs.append((P0 / "lib" / f"{name}.combined.lib", data, digest))
    for path, data, digest in outputs:
        if path.exists() and path.read_bytes() != data:
            raise SystemExit(f"BLOCKED: refusing to overwrite different local input {path}")
    for path, data, digest in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        print(f"PASS: {path.name} SHA256 {digest}")


if __name__ == "__main__":
    main()
