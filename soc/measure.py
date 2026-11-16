#!/usr/bin/env python3
"""Re-export fixed local OpenTitan dependencies and map actual blocks to GF180."""
import argparse, os, pathlib, subprocess, sys, json, hashlib, shlex
p=argparse.ArgumentParser(); p.add_argument('target',choices=['ibex','usbdev','debug','rom','boundary','dtm']);p.add_argument('--export',action='store_true');a=p.parse_args()
r=pathlib.Path(__file__).resolve().parent.parent; os.chdir(r)
ot=pathlib.Path(os.environ.get('OPENTITAN',str(r.parent/'opentitan'))).resolve()
expected='2e20836f9c9787bad82c84b5ba704223f06c8890'
assert subprocess.check_output(['git','-C',str(ot),'rev-parse','HEAD'],text=True).strip()==expected,'OpenTitan revision mismatch'
b=r/'soc/build';b.mkdir(exist_ok=True)
base='usbdev' if a.target in ['usbdev','debug','dtm'] else 'ibex'
if a.export:
 env=dict(os.environ,PYTHONPATH=str(r/'soc/.tools'))
 subprocess.run([sys.executable,str(r/'soc/.tools/bin/fusesoc'),'--cores-root='+str(ot),'--cores-root=soc','run','--setup','opendonz:measure:'+base],env=env,check=True)
import yaml
d=r/f'build/opendonz_measure_{base}_0.1/default-yosys'; e=yaml.safe_load((d/f'opendonz_measure_{base}_0.1.eda.yml').read_text())
files=[];incs=[]
for f in e['files']:
 q=(d/f['name']).resolve()
 if f.get('is_include_file'):incs.append(str(q.parent))
 elif f.get('file_type') in ['systemVerilogSource','verilogSource']:files.append(str(q))
top={'ibex':'ibex_top','usbdev':'usbdev','debug':'dm_top','dtm':'dmi_jtag','rom':'firmware_rom','boundary':'soc_boundary_top'}[a.target]
params=' -G RV32ZC=ibex_pkg::RV32Zca' if a.target=='ibex' else ''
if a.target=='rom':
 from elftools.elf.elffile import ELFFile
 with (r/'firmware/build/u2f.elf').open('rb') as f:
  elf=ELFFile(f); image=bytearray(32768)
  for seg in elf.iter_segments():
   if seg['p_type']=='PT_LOAD' and seg['p_paddr']<32768:
    start=seg['p_paddr'];image[start:start+seg['p_filesz']]=seg.data()
 lines=['module firmware_rom(input logic [12:0] addr_i, output logic [31:0] data_o);','always_comb case(addr_i)']
 for i in range(0,len(image),4):
  val=int.from_bytes(image[i:i+4],'little')
  if val:lines.append(f"13'd{i//4}: data_o = 32'h{val:08x};")
 lines+=['default: data_o=0;','endcase','endmodule']
 q=b/'firmware_rom.sv';q.write_text('\n'.join(lines)+'\n');files=[str(q)];incs=[]
if a.target=='boundary':
 # Append protocol engine closure from the existing P0 source boundary.
 ud=r/'build/opendonz_measure_usbdev_0.1/default-yosys'; ue=yaml.safe_load((ud/'opendonz_measure_usbdev_0.1.eda.yml').read_text())
 for f in ue['files']:
  if 'usb_fs_nb_pe' in f['name'] and not f.get('is_include_file'):files.append(str((ud/f['name']).resolve()))
 files += [str(r/'p0/src/usb_fs_nb_pe_top.sv'),str(r/'soc/rtl/soc_boundary_top.sv')]
lib=r/'p0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.combined.lib'
read='read_slang --ignore-initial --top '+top+params+' -DSYNTHESIS -DASSERT(__name,__prop)= '+' '.join('-I'+x for x in dict.fromkeys(incs))+' '+' '.join(files)
script=read+'\n'+f'hierarchy -check -top {top}; synth -top {top}; dfflibmap -liberty {lib}; abc -liberty {lib}; stat -liberty {lib}; write_verilog {b}/{a.target}-mapped.v\n'
ys=b/(a.target+'-read.ys');ys.write_text(script)
cmd=[os.environ.get('YOSYS','yosys'),'-m',os.environ.get('SLANG_PLUGIN','slang'),'-s',str(ys)]
with (b/(a.target+'-gf180.log')).open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
manifest={f:hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest() for f in files}
manifest.update(liberty_sha256=hashlib.sha256(lib.read_bytes()).hexdigest(),opentitan_commit=expected,command=shlex.join(cmd))
(b/(a.target+'-inputs.json')).write_text(json.dumps(manifest,indent=2)+'\n')
print(b/(a.target+'-gf180.log'))
