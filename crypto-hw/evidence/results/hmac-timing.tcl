read_liberty /Users/zxy/OpenDonz/p0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.combined.lib
read_verilog /Users/zxy/OpenDonz/crypto-hw/build/hmac/mapped.v
link_design hmac
create_clock -name core -period 41.6667 [get_ports clk_i]
set_input_delay 2 -clock core [all_inputs]
set_output_delay 2 -clock core [all_outputs]
report_checks -path_delay max -group_path_count 3
report_clock_min_period
exit
