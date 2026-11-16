#!/usr/bin/env python3
"""Fetch pinned alternative macro views and record capacity/area lower bounds."""
import hashlib,json,pathlib,re,subprocess
R=pathlib.Path(__file__).resolve().parent;D=R/'evidence/sram-alternatives';D.mkdir(parents=True,exist_ok=True)
REV='d41c7447d34d0c298158094378c8268560941724';rows=[]
for depth in [512]:
 cell=f'gf180mcu_ocd_ip_sram__sram{depth}x8m8wm1';views=[]
 for ext in ['.v','.blackbox.v','.lef','__tt_025C_3v30.lib']:
  src=f'cells/{cell}/{cell}{ext}';dest=D/(cell+ext)
  if not dest.exists():dest.write_bytes(subprocess.check_output(['gh','api',f'repos/RTimothyEdwards/gf180mcu_ocd_ip_sram/contents/{src}?ref={REV}','-H','Accept: application/vnd.github.raw+json']))
  data=dest.read_bytes();views.append(dict(source=src,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
 lef=(D/(cell+'.lef')).read_text();x,y=map(float,re.search(r'SIZE\s+([\d.]+)\s+BY\s+([\d.]+)',lef).groups());area=x*y
 rows.append(dict(cell=cell,depth=depth,width=8,area_um2=area,macros_full_dmem=39*(1024//depth),full_dmem_area_um2=area*39*(1024//depth),macros_half_dmem=39*((512+depth-1)//depth),half_dmem_area_um2=area*39*((512+depth-1)//depth),platform_acceptance='NOT confirmed; template selector is not shuttle signoff',views=views))
(D/'manifest.json').write_text(json.dumps(dict(commit=REV,license='Apache-2.0; see ../sram/LICENSE',macros=rows),indent=2)+'\n');print(json.dumps(rows,indent=2))
