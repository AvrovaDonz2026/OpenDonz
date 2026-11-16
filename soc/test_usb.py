#!/usr/bin/env python3
"""Digital line-level USB host against actual Ibex firmware + USB PE."""
import pathlib, subprocess, os, json, hashlib, yaml
r=pathlib.Path(__file__).resolve().parent.parent
b=r/'soc/build'; files=[];incs=[]
for name in ['ibex','usbdev']:
 d=r/f'build/opendonz_measure_{name}_0.1/default-yosys'
 e=yaml.safe_load((d/f'opendonz_measure_{name}_0.1.eda.yml').read_text())
 for f in e['files']:
  p=(d/f['name']).resolve()
  if f.get('is_include_file'):incs.append(str(p.parent))
  elif f.get('file_type') in ['systemVerilogSource','verilogSource'] and ('usb_fs' in str(p) or name=='ibex'):
   if p.name not in [pathlib.Path(x).name for x in files]:files.append(str(p))
files += [str(b/'firmware_rom.sv'),str(r/'p0/src/usb_fs_nb_pe_top.sv')]+[str(r/'soc/rtl'/n) for n in ['soc_memory_mailbox.sv','soc_firmware_top.sv','usb_u2f_bridge.sv','soc_usb_top.sv']]
cmd=[os.environ.get('VERILATOR','verilator'),'--cc','--exe','--build','-j','4','-Wno-fatal','-DSYNTHESIS','--top-module','soc_usb_top','--Mdir',str(b/'obj_usb'),*['-I'+i for i in dict.fromkeys(incs)],*files,str(r/'soc/dv/usb_soc_test.cpp')]
with (b/'usb-verilator-build.log').open('w') as f:
 result=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
if result.returncode:raise SystemExit('Verilator build failed; see soc/build/usb-verilator-build.log')
p=subprocess.run([str(b/'obj_usb/Vsoc_usb_top')],capture_output=True,text=True)
(b/'usb-rtl.log').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr);p.check_returncode()
files += [str(r/'soc/dv/usb_soc_test.cpp'),str(pathlib.Path(__file__).resolve())]
report=dict(status='PASS',test=p.stdout.strip(),checks=['device/configuration/HID report descriptors and independent CRC16','SET_ADDRESS status delayed until host ACK; missing-ACK retry','SET_CONFIGURATION; actual firmware INIT and VERSION','bad OUT CRC rejected; duplicate OUT suppressed','unsupported request STALL and subsequent SETUP recovery','short descriptor request; link reset; descriptor retry'],elf_sha256=hashlib.sha256((r/'firmware/build/u2f.elf').read_bytes()).hexdigest(),inputs={f:hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest() for f in files},limitations='Digital external reset signal; no analog PHY/link reset detector/pullup/VBUS; unassigned development VID/PID; NONPERSISTENT NVM STUB: erased reads / acknowledged discarded writes; deterministic test-only external RNG; no registration/authentication/persistence or physical implementation signoff')
(r/'soc/evidence/usb-rtl.json').write_text(json.dumps(report,indent=2)+'\n')
