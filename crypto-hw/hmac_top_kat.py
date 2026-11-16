#!/usr/bin/env python3
"""Exercise the actual exported HMAC top-level RTL through integrity-protected TL-UL."""
import pathlib,yaml
from rtl_tests import test,R
b=R/'build/hmac/opendonz_crypto_hmac_0.1/default-yosys'
d=yaml.safe_load((b/'opendonz_crypto_hmac_0.1.eda.yml').read_text());files=[];inc=[]
for f in d['files']:
 p=b/f['name']
 if f.get('is_include_file'):inc.append('-I'+str(p.parent))
 elif f.get('file_type') in ('systemVerilogSource','verilogSource'):files.append(p)
test('hmac-top-kat','hmac_top_kat_tb',files+[R/'rtl/hmac_top_kat_tb.sv'],list(dict.fromkeys(inc)))
