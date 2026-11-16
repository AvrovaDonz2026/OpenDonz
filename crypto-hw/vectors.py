#!/usr/bin/env python3
"""Build unmodified upstream OTBN P256 test ELFs and check upstream vectors."""
import json, os, pathlib, subprocess, sys, time
from elftools.elf.elffile import ELFFile
R=pathlib.Path(__file__).resolve().parent; OT=pathlib.Path('/Users/zxy/opentitan'); B=R/'build/vectors'; B.mkdir(parents=True,exist_ok=True)
E=dict(os.environ,PYTHONPATH=':'.join(str(OT/p) for p in ['.','util','hw/ip/otbn/util','hw/ip/otbn/dv/otbnsim']),RV32_TOOL_AS='/opt/homebrew/bin/riscv64-elf-as',RV32_TOOL_LD='/opt/homebrew/bin/riscv64-elf-ld')
PY=sys.executable; U=OT/'hw/ip/otbn/util'; C=OT/'sw/otbn/crypto'
def run(cmd,log):
    with log.open('w') as f: subprocess.run(cmd,env=E,stdout=f,stderr=subprocess.STDOUT,check=True)
def main():
    rows=[]
    for name,extra in [('p256_base_mult_test',[]),('p256_key_from_seed_test',[]),('p256_ecdsa_sign_test',['p256_sign']),('p256_ecdsa_verify_test',['p256_verify'])]:
        sources=[C/'tests'/f'{name}.s']+[C/f'{x}.s' for x in ['p256_base','p256_b2a','p256_isoncurve']+extra]
        objs=[]
        for s in sources:
            obj=B/(s.stem+'.o'); run([PY,str(U/'otbn_as.py'),'-march=rv32i_zicsr','-o',str(obj),str(s)], B/(s.stem+'-as.log')); objs.append(str(obj))
        elf=B/(name+'.elf'); run([PY,str(U/'otbn_ld.py'),'-m','elf32lriscv','-o',str(elf)]+objs,B/(name+'-ld.log'))
        sim=OT/'hw/ip/otbn/dv/otbnsim/standalone.py'
        # simulator executable wrapper lives locally, upstream Python sources stay unchanged.
        wrapper=B/'sim'; wrapper.write_text('#!/bin/sh\nexec '+PY+' '+str(sim)+' "$@"\n'); wrapper.chmod(0o755)
        start=time.monotonic()
        run([PY,str(U/'otbn_sim_test.py'),str(wrapper),'--expected_regs',str(C/'tests'/f'{name}.exp'),'--dump-regs',str(elf)],B/(name+'-test.log'))
        run([PY,str(sim),str(elf),'--dump-regs',str(B/(name+'-regs.txt')),'--dump-dmem',str(B/(name+'-dmem.bin')),'--dump-stats',str(B/(name+'-stats.txt'))],B/(name+'-sim.log'))
        with elf.open('rb') as f:
            e=ELFFile(f); sections={s.name:s['sh_size'] for s in e.iter_sections() if s.name in ['.text','.data','.bss']}
        rows.append(dict(test=name,upstream_vector='PASS',sections_bytes=sections,host_seconds_two_runs=time.monotonic()-start,cycle_source='Python ISA model only; NOT RTL cycles'))
        (B/'results.json').write_text(json.dumps(rows,indent=2)+'\n'); print(name,'PASS',flush=True)
if __name__=='__main__': main()
