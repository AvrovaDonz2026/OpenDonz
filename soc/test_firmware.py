#!/usr/bin/env python3
"""Execute locked actual Ibex + firmware via Verilator; external packet interface."""
import pathlib, subprocess, os, json, hashlib, yaml
r=pathlib.Path(__file__).resolve().parent.parent
b=r/'soc/build';d=r/'build/opendonz_measure_ibex_0.1/default-yosys'
e=yaml.safe_load((d/'opendonz_measure_ibex_0.1.eda.yml').read_text())
files=[];incs=[]
for f in e['files']:
 p=(d/f['name']).resolve()
 if f.get('is_include_file'):incs.append(str(p.parent))
 elif f.get('file_type') in ['systemVerilogSource','verilogSource']:files.append(str(p))
files += [str(b/'firmware_rom.sv')]+[str(r/'soc/rtl'/n) for n in ['soc_memory_mailbox.sv','soc_firmware_top.sv','tb_firmware.sv']]
cmd=[os.environ.get('VERILATOR','verilator'),'--binary','--timing','-j','4','-Wno-fatal','-DSYNTHESIS','--top-module','tb_firmware','--Mdir',str(b/'obj_firmware'),*['-I'+i for i in dict.fromkeys(incs)],*files]
with (b/'firmware-verilator-build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
p=subprocess.run([str(b/'obj_firmware/Vtb_firmware')],capture_output=True,text=True)
(b/'firmware-rtl.log').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr);p.check_returncode()
report=dict(status='PASS',test='actual Ibex reset/startup/HID INIT/U2F_VERSION using actual firmware ROM',elf_sha256=hashlib.sha256((r/'firmware/build/u2f.elf').read_bytes()).hexdigest(),inputs={f:hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest() for f in files},limitations='Packet mailbox input only: no USB PE/EP0/enumeration, persistent NVM, qualified entropy, physical SRAM or debug interconnect; not full U2F SoC')
(r/'soc/evidence/firmware-rtl.json').write_text(json.dumps(report,indent=2)+'\n')
