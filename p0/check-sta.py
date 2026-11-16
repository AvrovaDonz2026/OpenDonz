#!/usr/bin/env python3
"""Compatibility entry point for the authoritative timing/coverage checker."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parent / "sta" / "check-results.py"),
               run_name="__main__")
