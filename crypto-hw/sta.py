#!/usr/bin/env python3
"""Run reproducible diagnostic STA, including pinned macro Liberty (not signoff)."""
import argparse,pathlib,subprocess
R=pathlib.Path(__file__).resolve().parent
STA='/nix/store/s2g847svsh7lf0gkz0n1z1y6bq3lk95v-opensta/bin/sta'
def main():
 p=argparse.ArgumentParser();p.add_argument('block',choices=['otbn','otbn8','hmac']);a=p.parse_args()
 b=R/'build'/a.block;assert (b/'mapped.v').exists()
 lines=['read_liberty '+str(R.parent/'p0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.combined.lib')]
 if a.block!='hmac':lines+=['read_liberty '+str(R/'evidence/sram/gf180mcu_ocd_ip_sram__sram1024x8m8wm1__tt_025C_3v30.lib')]
 lines+=['read_verilog '+str(b/'mapped.v'),'link_design '+('hmac' if a.block=='hmac' else 'otbn'),'create_clock -name core -period 41.6667 [get_ports clk_i]']
 if a.block!='hmac':lines+=['create_clock -name edn -period 41.6667 [get_ports clk_edn_i]','create_clock -name otp -period 41.6667 [get_ports clk_otp_i]']
 if a.block!='hmac':lines+=['set_input_delay 2 -clock core [get_ports {rst_ni tl_i* alert_rx_i* lc_escalate_en_i* lc_rma_req_i* ram_cfg_imem_i* ram_cfg_dmem_i* keymgr_key_i* kmac_app_i* keymgr_app_i* keymgr_sensitive_key_i*}]','set_input_delay 2 -clock edn [get_ports {rst_edn_ni edn_rnd_i* edn_urnd_i*}]','set_input_delay 2 -clock otp [get_ports {rst_otp_ni otbn_otp_key_i*}]']
 else:lines+=['set_input_delay 2 -clock core [all_inputs]']
 lines+=['set_output_delay 2 -clock core [all_outputs]','report_checks -path_delay max -group_path_count 3','report_clock_min_period','exit']
 (b/'timing.tcl').write_text('\n'.join(lines)+'\n')
 with (b/'timing.log').open('w') as f:subprocess.run([STA,'-exit',str(b/'timing.tcl')],stdout=f,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__':main()
