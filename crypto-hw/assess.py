#!/usr/bin/env python3
"""Isolated, pinned OpenTitan crypto closure export and GF180 mapping."""
import argparse, hashlib, json, os, pathlib, subprocess, sys
import yaml
R = pathlib.Path(__file__).resolve().parent
OT = pathlib.Path('/Users/zxy/opentitan')
REV = '2e20836f9c9787bad82c84b5ba704223f06c8890'
LIB = R.parent/'p0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.combined.lib'
YOSYS = '/nix/store/3gz0fa36lbx3a699lhgigzdv48kzff7w-yosys-with-plugins-0.69/bin/yosys'
SLANG = '/nix/store/rssz08b5s5k616wf55aqifx7ymicxwr2-yosys-slang/share/yosys/plugins/slang.so'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('block',choices=['otbn','hmac']); ap.add_argument('--map',action='store_true'); ap.add_argument('--macros',action='store_true'); ap.add_argument('--imem8',action='store_true'); ap.add_argument('--half-dmem',action='store_true'); a=ap.parse_args(); a.imem8 |= a.half_dmem
    assert subprocess.check_output(['git','-C',str(OT),'rev-parse','HEAD'],text=True).strip()==REV
    b=R/'build'/('otbn8-dmem16' if a.half_dmem else 'otbn8' if a.imem8 else a.block); b.mkdir(parents=True,exist_ok=True)
    cmd=[str(R/'.venv/bin/fusesoc'),'--cores-root='+str(OT),'--cores-root='+str(R),'run','--target=default','--setup','--build-root='+str(b),'opendonz:crypto:'+a.block]
    with (b/'export.log').open('w') as f:
        subprocess.run(cmd,cwd=R,stdout=f,stderr=subprocess.STDOUT,check=True)
    eda=next(b.rglob('*.eda.yml')); export_root=eda.parent; data=yaml.safe_load(eda.read_text()); files=[]; inc=[]; manifest=[]
    for f in data['files']:
        p=(export_root/f['name']).resolve()
        if p.exists():
            manifest.append(dict(path=str(p.relative_to(R)),sha256=sha(p),file_type=f.get('file_type'),include=f.get('is_include_file',False)))
        if f.get('is_include_file'): inc.append(str(p.parent))
        elif f.get('file_type') in ['systemVerilogSource','verilogSource']: files.append(str(p))
    (b/'inputs.json').write_text(json.dumps(dict(opentitan_commit=REV,liberty=str(LIB),liberty_sha256=sha(LIB),files=manifest,export_command=cmd),indent=2)+'\n')
    if a.imem8:
        assert a.block=='otbn'
        from configure import prepare
        prepare(a.half_dmem)
        overlay=R/'build'/('imem8-dmem16' if a.half_dmem else 'imem8')/'otbn'
        files=[str(overlay/'rtl'/pathlib.Path(x).name) if pathlib.Path(x).name in ('otbn_reg_pkg.sv','otbn_reg_top.sv','otbn_pkg.sv') else x for x in files]
    if a.macros:
        files=[str(R/'rtl/prim_ram_1p.sv') if pathlib.Path(x).name=='prim_ram_1p.sv' else x for x in files]
        files.insert(0,str(R/'evidence/sram/gf180mcu_ocd_ip_sram__sram1024x8m8wm1.blackbox.v'))
        files.insert(0,str(R/'evidence/sram-alternatives/gf180mcu_ocd_ip_sram__sram512x8m8wm1.blackbox.v'))
    prefix=R/'rtl/prelude.sv'; prefix.write_text('`include "prim_assert.sv"\n`include "prim_flop_macros.sv"\n')
    files.insert(0,str(prefix))
    read='read_slang --empty-blackboxes --single-unit --ignore-initial --top '+a.block+' -DSYNTHESIS -DASSERT(__name,__prop)= '+' '.join('-I'+x for x in dict.fromkeys(inc))+' '+' '.join(files)
    macro_check='select -assert-count '+str(49 if a.imem8 else 59)+' t:gf180mcu_ocd_ip_sram__sram1024x8m8wm1; select -clear; ' if a.macros and a.block=='otbn' else ''
    if a.half_dmem:
        macro_check='select -assert-count 10 t:gf180mcu_ocd_ip_sram__sram1024x8m8wm1; select -assert-count 39 t:gf180mcu_ocd_ip_sram__sram512x8m8wm1; select -clear; '
    script=read+'\nhierarchy -check -top '+a.block+'; '+macro_check+'synth -top '+a.block+'; dfflibmap -liberty '+str(LIB)+'; abc -liberty '+str(LIB)+'; '+macro_check+'stat -liberty '+str(LIB)+'; write_verilog '+str(b/'mapped.v')+'\n'
    (b/'map.ys').write_text(script)
    if a.map:
        with (b/'gf180.log').open('w') as f: subprocess.run([YOSYS,'-m',SLANG,'-s',str(b/'map.ys')],stdout=f,stderr=subprocess.STDOUT,check=True)
    (b/'effective-inputs.json').write_text(json.dumps(dict(imem_bytes=8192 if a.imem8 else 16384,dmem_bus_bytes=8192 if a.half_dmem else 16384,dmem_total_bytes=16384 if a.half_dmem else 32768,macro_count=49 if a.imem8 else 59,macro_organization={"1024x8":10,"512x8":39} if a.half_dmem else {"1024x8":49 if a.imem8 else 59},files=[dict(path=x,sha256=sha(pathlib.Path(x))) for x in files]),indent=2)+'\n')
    print(eda)
if __name__=='__main__': main()
