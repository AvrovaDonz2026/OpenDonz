#!/usr/bin/env python3
"""Snapshot OTBN8 closure; compare only official FeatStubMai parameter."""
import hashlib,json,pathlib,shlex,subprocess,sys
R=pathlib.Path(__file__).resolve().parents[2]
B=pathlib.Path(__file__).resolve().parent
Y='/nix/store/3gz0fa36lbx3a699lhgigzdv48kzff7w-yosys-with-plugins-0.69/bin/yosys'
P='/nix/store/rssz08b5s5k616wf55aqifx7ymicxwr2-yosys-slang/share/yosys/plugins/slang.so'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare():
 old=R/'crypto-hw/build/otbn8/map.ys'; text=old.read_text(); first=text.splitlines()[0]; tokens=shlex.split(first); manifest=[]
 for i,t in enumerate(tokens):
  if t.startswith('/') and pathlib.Path(t).is_file():
   src=pathlib.Path(t); dst=B/'inputs'/str(i)/src.name; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(src.read_bytes()); text=text.replace(t,str(dst)); manifest.append(dict(original=t,snapshot=str(dst),sha256=sha(dst)))
 # Include directories are snapshotted too, to avoid concurrent worker edits.
 for i,t in enumerate(tokens):
  if t.startswith('-I'):
   src=pathlib.Path(t[2:]); dst=B/'includes'/str(i); dst.mkdir(parents=True,exist_ok=True)
   for p in src.iterdir():
    if p.is_file():
     copy=dst/p.name;copy.write_bytes(p.read_bytes());manifest.append(dict(original=str(p),snapshot=str(copy),sha256=sha(copy)))
   text=text.replace(t,'-I'+str(dst))
 lib=R/'p0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.combined.lib'
 (B/'manifest.json').write_text(json.dumps(dict(source_script_sha256=sha(old),files=manifest,liberty_sha256=sha(lib),memory='8KiB IMEM + 32KiB total DMEM; 49 OCD 1024x8 macros',sole_rtl_parameter='FeatStubMai'),indent=2)+'\n')
 for name,value in [('baseline',0),('stub',1)]:
  out=B/name;out.mkdir(exist_ok=True)
  s=text.replace('--top otbn','--top otbn -GFeatStubMai='+str(value),1)
  s=s.replace(str(R/'crypto-hw/build/otbn8/mapped.v'),str(out/'mapped.v'))
  s=s.replace('; stat -liberty','; select -assert-count 49 t:gf180mcu_ocd_ip_sram__sram1024x8m8wm1; select -clear; stat -liberty')
  (out/'map.ys').write_text(s)
def timing(name):
 out=B/name
 source=(R/'crypto-hw/build/otbn8/timing.tcl').read_text()
 source=source.replace(str(R/'crypto-hw/build/otbn8/mapped.v'),str(out/'mapped.v'))
 (out/'timing.tcl').write_text(source)
 with (out/'timing.log').open('w') as f:
  subprocess.run(['/nix/store/s2g847svsh7lf0gkz0n1z1y6bq3lk95v-opensta/bin/sta','-exit',str(out/'timing.tcl')],stdout=f,stderr=subprocess.STDOUT,check=True)
def run(name):
 out=B/name
 with (out/'gf180.log').open('w') as f:subprocess.run([Y,'-m',P,'-s',str(out/'map.ys')],stdout=f,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 elif sys.argv[1]=='timing':timing(sys.argv[2])
 else:run(sys.argv[1])
