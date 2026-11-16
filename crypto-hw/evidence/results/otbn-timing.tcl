read_liberty /Users/zxy/OpenDonz/p0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.combined.lib
read_liberty /Users/zxy/OpenDonz/crypto-hw/evidence/sram/gf180mcu_ocd_ip_sram__sram1024x8m8wm1__tt_025C_3v30.lib
read_verilog /Users/zxy/OpenDonz/crypto-hw/build/otbn/mapped.v
link_design otbn
create_clock -name core -period 41.6667 [get_ports clk_i]
create_clock -name edn -period 41.6667 [get_ports clk_edn_i]
create_clock -name otp -period 41.6667 [get_ports clk_otp_i]
set_input_delay 2 -clock core [get_ports {rst_ni tl_i* alert_rx_i* lc_escalate_en_i* lc_rma_req_i* ram_cfg_imem_i* ram_cfg_dmem_i* keymgr_key_i* kmac_app_i* keymgr_app_i* keymgr_sensitive_key_i*}]
set_input_delay 2 -clock edn [get_ports {rst_edn_ni edn_rnd_i* edn_urnd_i*}]
set_input_delay 2 -clock otp [get_ports {rst_otp_ni otbn_otp_key_i*}]
set_output_delay 2 -clock core [all_outputs]
report_checks -path_delay max -group_path_count 3
report_clock_min_period
exit
