#!/usr/bin/env python3
"""Compile small real RTL tests; avoid Verilator make archive xargs on macOS sandbox."""
import pathlib,subprocess
R=pathlib.Path(__file__).resolve().parent;OT=pathlib.Path('/Users/zxy/opentitan');V='/nix/store/vvqlbab2xl9y19cnahq64rgk1if72klr-verilator-5.046/bin/verilator';P=OT/'hw/ip/prim/rtl'
def test(name,top,files,options=[]):
 b=R/'build'/name;b.mkdir(parents=True,exist_ok=True)
 cmd=[V,'--output-split','0','--cc','--main','--exe','--timing','-Wno-fatal','--top-module',top,'--Mdir',str(b),'-I'+str(P)]+options+list(map(str,files))
 with (b/'build.log').open('w') as f:
  subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
  subprocess.run(['make','-C',str(b),'-f','V'+top+'.mk','V'+top+'__ALL.o','verilated.o','verilated_timing.o','verilated_threads.o'],stdout=f,stderr=subprocess.STDOUT,check=True)
  subprocess.run(['ar','rcs',str(b/('V'+top+'__ALL.a')),str(b/('V'+top+'__ALL.o'))],stdout=f,stderr=subprocess.STDOUT,check=True)
  subprocess.run(['make','-C',str(b),'-f','V'+top+'.mk','V'+top],stdout=f,stderr=subprocess.STDOUT,check=True)
 with (b/'result.log').open('w') as f:subprocess.run([str(b/('V'+top))],stdout=f,stderr=subprocess.STDOUT,check=True)
 print(name,'PASS',flush=True)
if __name__=='__main__':
 test('sha-kat','sha_kat_tb',[P/x for x in ['prim_sha2_pkg.sv','prim_sha2_pad.sv','prim_sha2.sv','prim_sha2_32.sv']]+[R/'rtl/sha_kat_tb.sv'])
 for name,width,depth in [('macro8',39,2048),('macro-dmem',312,1024)]:
  test(name,'macro_tb',[OT/'hw/ip/prim_generic/rtl/prim_ram_1p_pkg.sv',R/'evidence/sram/gf180mcu_ocd_ip_sram__sram1024x8m8wm1.v',R/'rtl/prim_ram_1p.sv',R/'rtl/macro_tb.sv'],[f'-GWidth={width}',f'-GDepth={depth}'])
