#!/usr/bin/env python3
"""Real Liberty/OpenSTA pass/fail smoke fixture; never alters PE constraints."""
import os
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parent
out=root/'reports'/'sta-gate-fixture'
out.mkdir(exist_ok=True)
# A short real mapped data path; four actual buffers delay external reset.
net=out/'fixture.v'
net.write_text("module usb_fs_nb_pe_top(input clk_i,rst_ni,d,usb_d_i,usb_dp_i,usb_dn_i,output q);\nwire r0,r1,r2,r3,x0,x1,x2;\n" + "\n".join(f"gf180mcu_fd_sc_mcu7t5v0__buf_1 b{i} (.I({'rst_ni' if i==0 else 'r'+str(i-1)}), .Z(r{i}));" for i in range(4)) + "\ngf180mcu_fd_sc_mcu7t5v0__xor2_1 xora (.A1(d),.A2(usb_d_i),.Z(x0));\ngf180mcu_fd_sc_mcu7t5v0__xor2_1 xorb (.A1(x0),.A2(usb_dp_i),.Z(x1));\ngf180mcu_fd_sc_mcu7t5v0__xor2_1 xorc (.A1(x1),.A2(usb_dn_i),.Z(x2));\ngf180mcu_fd_sc_mcu7t5v0__dffrnq_1 ff (.CLK(clk_i),.RN(r3),.D(x2),.Q(q));\nendmodule\n")
for corner in ('tt_025C_3v30','ss_125C_3v00'):
    prefix=out/corner
    log=out/(corner+'.log')
    env=dict(os.environ,STA_TOP='usb_fs_nb_pe_top',STA_CORNER=corner,STA_LIB=str(root/'lib'/('gf180mcu_fd_sc_mcu7t5v0__'+corner+'.combined.lib')),STA_NETLIST=str(net),STA_SDC=str(root/'sta'/'usb-fs-pe.sdc'),STA_PREFIX=str(prefix))
    with log.open('w') as f:
        subprocess.run(['sta','-no_splash','-exit',str(root/'sta'/'run.tcl')],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    result=subprocess.run(['python3',str(root/'sta'/'check-results.py'),str(prefix),str(log)])
    if result.returncode != 0: raise SystemExit(result.returncode)
# The exact same checker must reject actual library removal violations.
    bad=out/'fixture-bad.v'
    bad.write_text(net.read_text().replace('.RN(r3)', '.RN(rst_ni)'))
    env['STA_NETLIST']=str(bad)
    env['STA_PREFIX']=str(prefix)+'-bad'
    badlog=out/(corner+'-bad.log')
    with badlog.open('w') as f:
        subprocess.run(['sta','-no_splash','-exit',str(root/'sta'/'run.tcl')],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    result=subprocess.run(['python3',str(root/'sta'/'check-results.py'),env['STA_PREFIX'],str(badlog)])
    if result.returncode != 1: raise SystemExit('Negative fixture must return 1')
print('Real mapped fixtures: pass=0 and actual removal failure=1, both corners, original SDC')
