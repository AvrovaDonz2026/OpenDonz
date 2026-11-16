#!/usr/bin/env python3
"""Persist half-DMEM evidence only after each producer has successfully completed."""
import pathlib,json,hashlib,shutil
R=pathlib.Path(__file__).resolve().parent;E=R/'evidence/results';E.mkdir(exist_ok=True)
items={'imem8-dmem16/configuration.json':'half-configuration.json','p256-imem8-dmem16/results.json':'p256-half.json','boundaries-half/results.json':'boundaries-half.json','hmac-top-kat/result.log':'hmac-top-kat.log','otbn-full-generic/result.log':'otbn-full-generic.log','otbn-full-macros/result.log':'otbn-full-macros.log','otbn8-dmem16/gf180.log':'half-gf180.log','otbn8-dmem16/timing.log':'half-timing.log','otbn8-dmem16/timing.tcl':'half-timing.tcl','otbn8-dmem16/effective-inputs.json':'half-effective-inputs.json'}
items.update({f'{name}/result.log':f'{name}-half.log' for name in ('macro8','macro-dmem','macro-half-dmem')})
for src,dst in items.items():
 p=R/'build'/src
 assert p.exists(),p
 if 'full-' in src:assert 'independent cryptography/OpenSSL' in p.read_text(),p
 shutil.copyfile(p,E/dst)
net=R/'build/otbn8-dmem16/mapped.v'
(E/'half-netlist.json').write_text(json.dumps(dict(path=str(net),sha256=hashlib.sha256(net.read_bytes()).hexdigest()),indent=2)+'\n')
