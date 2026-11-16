#!/usr/bin/env python3
"""Hash local assessment sources and durable evidence, excluding this manifest."""
import hashlib,json,pathlib
R=pathlib.Path(__file__).resolve().parent
out=R/'evidence/assessment-local-sha256.json'
files=[p for p in R.rglob('*') if p.is_file() and not any(x in p.relative_to(R).parts for x in ('build','.venv','__pycache__')) and p!=out]
files+=[R.parent/'docs/opentitan-crypto-assessment.md']
out.write_text(json.dumps([dict(path=str(p.relative_to(R.parent)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(files)],indent=2)+'\n')
