#!/usr/bin/env python3
"""Build complete OTBN IP with TL-UL, ECC, scrambling and active secure wipe."""
import pathlib,json,yaml,sys,os,subprocess
from cryptography.hazmat.primitives.asymmetric import ec,utils
from cryptography.hazmat.primitives import hashes
import rtl_tests
from elftools.elf.elffile import ELFFile
R=rtl_tests.R
toolroot=pathlib.Path(os.environ.get('OTBN_VERILATOR_ROOT',str(R/'build/tools/verilator-verilator-2f2fae5')))
os.environ['VERILATOR_ROOT']=str(toolroot)
V=toolroot/'bin/verilator'
rtl_tests.V=str(V)
b=R/'build/otbn8-dmem16/opendonz_crypto_otbn_0.1/default-yosys'
d=yaml.safe_load((b/'opendonz_crypto_otbn_0.1.eda.yml').read_text());files=[];inc=[]
overlay=R/'build/imem8-dmem16/otbn/rtl'
for f in d['files']:
 p=b/f['name']
 if f.get('is_include_file'):inc.append('-I'+str(p.parent))
 elif f.get('file_type') in ('systemVerilogSource','verilogSource'):
  if p.name in ('otbn_pkg.sv','otbn_reg_pkg.sv','otbn_reg_top.sv'):p=overlay/p.name
  files.append(p)
# Default uses upstream generic RAM; --macros runs actual GF180 functional SRAM models.
if '--macros' in sys.argv:
 files=[R/'rtl/prim_ram_1p_model_hold.sv' if p.name=='prim_ram_1p.sv' else p for p in files]
 files[:0]=[R/'evidence/sram/gf180mcu_ocd_ip_sram__sram1024x8m8wm1.v',R/'evidence/sram-alternatives/gf180mcu_ocd_ip_sram__sram512x8m8wm1.v']
base_inputs={}
with (R/'build/p256-imem8-dmem16/run_p256.elf').open('rb') as ef:
 e=ELFFile(ef);symbols={x.name:x['st_value'] for x in e.get_section_by_name('.symtab').iter_symbols()}
 for name,base in [('.text',0x4000),('.data',0x8000)]:
  sec=e.get_section_by_name(name);raw=sec.data()
  for off in range(0,len(raw),4):base_inputs[base+sec['sh_addr']+off]=int.from_bytes(raw[off:off+4],'little')
 for off in range(0,8192,4):base_inputs.setdefault(0x8000+off,0)
# A real assembled program touches both ends of internal private scratch and copies back public results.
program=R/'build/private_boundary.s';program.write_text('.text\n.globl start\nstart:\n li x2,8192\n li x3,123\n sw x3,0(x2)\n lw x4,0(x2)\n sw x4,0(x0)\n li x2,16380\n sw x3,0(x2)\n lw x4,0(x2)\n sw x4,4(x0)\n ecall\n')
u=R/'build/imem8-dmem16/otbn/util'
env=os.environ.copy();env.update(PYTHONPATH=':'.join(map(str,[rtl_tests.OT,rtl_tests.OT/'util',u])),RV32_TOOL_AS='/opt/homebrew/bin/riscv64-elf-as',RV32_TOOL_LD='/opt/homebrew/bin/riscv64-elf-ld')
subprocess.run([sys.executable,str(u/'otbn_as.py'),'-march=rv32i_zicsr','-o',str(program.with_suffix('.o')),str(program)],env=env,check=True)
subprocess.run([sys.executable,str(u/'otbn_ld.py'),'-m','elf32lriscv','-o',str(program.with_suffix('.elf')),str(program.with_suffix('.o'))],env=env,check=True)
with program.with_suffix('.elf').open('rb') as f:
 raw=ELFFile(f).get_section_by_name('.text').data()
pinput=R/'build/full-rtl-private_boundary.txt';pinput.write_text(''.join(f'{0x4000+off:08x} {int.from_bytes(raw[off:off+4],"little"):08x}\n' for off in range(0,len(raw),4)))
pcheck=R/'build/full-rtl-private_boundary-expected.txt';pcheck.write_text('')
args=['+private_boundary='+str(pinput),'+private_boundary_expected='+str(pcheck)]
for name,outputs,error in [('base_mult',['x','y'],0),('sign',['r','s'],0),('verify',['ok','x_r'],0),('invalid_mode',[],8)]:
 inputs=base_inputs.copy()
 for label,raw in json.loads((R/f'build/p256-imem8-dmem16/{name}-inputs.json').read_text()).items():
  data=bytes.fromhex(raw)
  for off in range(0,len(data),4):inputs[0x8000+symbols[label]+off]=int.from_bytes(data[off:off+4],'little')
 f=R/f'build/full-rtl-{name}.txt';f.write_text(''.join(f'{a:08x} {v:08x}\n' for a,v in sorted(inputs.items())))
 # Randomized signing output need not match deterministic ISA entropy; base_mult and verify do.
 checks={}
 if name!='sign':
  raw=(R/f'build/p256-imem8-dmem16/{name}.bin').read_bytes()
  data=b''.join(raw[i+1:i+5] for i in range(0,len(raw),5))
  for label in outputs:
   start=symbols[label]
   for off in range(0,4 if label=='ok' else 32,4):checks[0x8000+start+off]=int.from_bytes(data[start+off:start+off+4],'little')
 fcheck=R/f'build/full-rtl-{name}-expected.txt';fcheck.write_text(''.join(f'{a:08x} {v:08x}\n' for a,v in checks.items()))
 args += [f'+{name}='+str(f),f'+{name}_expected='+str(fcheck)]
args += [f'+sig_r_addr={0x8000+symbols["r"]:x}',f'+sig_s_addr={0x8000+symbols["s"]:x}']
name='otbn-full-macros' if '--macros' in sys.argv else 'otbn-full-generic'
if '--run-only' in sys.argv:
 with (R/'build'/name/'result.log').open('w') as f:subprocess.run([str(R/'build'/name/'Votbn_full_tb')]+args,stdout=f,stderr=subprocess.STDOUT,check=True)
else:
 rtl_tests.test(name,'otbn_full_tb',files+[R/'rtl/otbn_full_tb.sv'],list(dict.fromkeys(inc))+['--unroll-count','72']+(['-DGF180_SIM_HOLD'] if '--macros' in sys.argv else []),args)
log=(R/'build'/('otbn-full-macros' if '--macros' in sys.argv else 'otbn-full-generic')/'result.log').read_text()
parts={}
for line in log.splitlines():
 if line.startswith('SIGNATURE '):
  _,label,value=line.split();parts[label]=int(value,16)
assert set(parts)=={'r','s'},'missing RTL signature readback'
ec.derive_private_key(7,ec.SECP256R1()).public_key().verify(utils.encode_dss_signature(parts['r'],parts['s']),bytes(range(32)),ec.ECDSA(utils.Prehashed(hashes.SHA256())))
with (R/'build'/('otbn-full-macros' if '--macros' in sys.argv else 'otbn-full-generic')/'result.log').open('a') as f:f.write('PASS independent cryptography/OpenSSL verification of actual RTL signature\n')
