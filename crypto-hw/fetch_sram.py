import hashlib,json,pathlib,subprocess
R=pathlib.Path(__file__).resolve().parent/'evidence/sram';R.mkdir(parents=True,exist_ok=True)
rev='d41c7447d34d0c298158094378c8268560941724';cell='gf180mcu_ocd_ip_sram__sram1024x8m8wm1'
paths=['LICENSE','README.rst']+['cells/'+cell+'/'+cell+x for x in ['.v','.blackbox.v','__tt_025C_3v30.lib','.lef']]+['cells/'+cell+'/specs/1_pins_desc.csv','cells/'+cell+'/specs/5_AC_Characteristics1.csv']
rows=[]
for p in paths:
 cmd=['gh','api','repos/RTimothyEdwards/gf180mcu_ocd_ip_sram/contents/'+p+'?ref='+rev,'-H','Accept: application/vnd.github.raw+json']
 data=subprocess.check_output(cmd);dest=R/pathlib.Path(p).name;dest.write_bytes(data);rows.append(dict(source=p,commit=rev,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
(R/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
