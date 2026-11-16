#!/usr/bin/env python3
"""Check isolated linker capacity and ISA exception paths (not RTL security proof)."""
import json,os,pathlib,subprocess,sys
R=pathlib.Path(__file__).resolve().parent;OT=pathlib.Path('/Users/zxy/opentitan');O=R/'build/imem8/otbn';U=O/'util';B=R/'build/boundaries';B.mkdir(parents=True,exist_ok=True)
paths=list(map(str,[OT,OT/'util',U,O/'dv/otbnsim']));sys.path[:0]=paths;os.environ.update(PYTHONPATH=':'.join(paths),RV32_TOOL_AS='/opt/homebrew/bin/riscv64-elf-as',RV32_TOOL_LD='/opt/homebrew/bin/riscv64-elf-ld')
from sim.load_elf import load_elf
from sim.standalonesim import StandaloneSim
rows=[]
def build(name,src,success=True):
 s=B/(name+'.s');s.write_text(src);obj=B/(name+'.o');elf=B/(name+'.elf')
 subprocess.run([sys.executable,str(U/'otbn_as.py'),'-march=rv32i_zicsr','-o',str(obj),str(s)],check=True)
 with (B/(name+'.log')).open('w') as f:r=subprocess.run([sys.executable,str(U/'otbn_ld.py'),'-m','elf32lriscv','-o',str(elf),str(obj)],stdout=f,stderr=subprocess.STDOUT)
 assert (r.returncode==0)==success
 rows.append(dict(test=name,link_success=success))
 return elf
elf=build('exact_8192','.text\n.globl start\nstart: ecall\n.zero 8188\n')
build('overflow_8196','.text\n.globl start\nstart: ecall\n.zero 8192\n',False)
for name,src,err in [('fetch_beyond_8192','li x2,8192\njalr x0,x2,0',2),('bad_dmem_addr','li x2,32768\nlw x3,0(x2)',1),('illegal_insn','unimp',8)]:
 elf=build(name,'.text\n.globl start\nstart: '+src+'\necall\n');sim=StandaloneSim();load_elf(sim,str(elf));sim.state.ext_regs.commit();sim.start(False);sim.run(False,None);got=sim.state.ext_regs.read('ERR_BITS',False);assert got==err,(name,got);rows[-1]['err_bits']=got
(B/'results.json').write_text(json.dumps(dict(layer='ISA and linker only; no hardware wipe/ECC fault proof',tests=rows),indent=2)+'\n');print(rows)
