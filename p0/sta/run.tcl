foreach name {STA_TOP STA_CORNER STA_LIB STA_NETLIST STA_SDC STA_PREFIX} {
  if {![info exists env($name)] || $env($name) eq ""} { error "Missing $name" }
}
read_liberty $env(STA_LIB)
read_verilog $env(STA_NETLIST)
link_design $env(STA_TOP)
read_sdc $env(STA_SDC)
set out $env(STA_PREFIX)
check_setup -verbose > "${out}-check_timing.rpt"
report_checks -path_delay max -group_path_count 10000 -format full_clock_expanded -fields {slew capacitance fanout input_pin net} -digits 4 > "${out}-setup.rpt"
report_checks -path_delay min -group_path_count 10000 -format full_clock_expanded -fields {slew capacitance fanout input_pin net} -digits 4 > "${out}-hold.rpt"
report_check_types -violators -max_delay -min_delay -recovery -removal -max_slew -max_capacitance -min_pulse_width -digits 4 > "${out}-violations.rpt"
report_checks -path_delay min_max -from [get_ports rst_ni] -group_path_count 100 -digits 4 > "${out}-reset.rpt"
report_checks -unconstrained -group_path_count 10000 -digits 4 > "${out}-unconstrained.rpt"
foreach port {usb_d_i usb_dp_i usb_dn_i} {
  report_checks -unconstrained -from [get_ports $port] -group_path_count 10000 -format full_clock_expanded -fields {slew capacitance fanout input_pin net} -digits 4 > "${out}-${port}.rpt"
}
report_worst_slack -max -digits 4 > "${out}-slack.rpt"
report_worst_slack -min -digits 4 >> "${out}-slack.rpt"
report_tns -digits 4 >> "${out}-slack.rpt"
set fp [open "${out}-slack.rpt" a]
puts $fp "P0_SETUP_SLACK [sta::worst_slack -max]"
puts $fp "P0_MIN_SLACK [sta::worst_slack -min]"
close $fp
puts "Reports written: $out"
exit
