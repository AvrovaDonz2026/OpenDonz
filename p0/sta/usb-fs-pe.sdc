# Digital PE boundary contract: synchronous RX/control/endpoint inputs.
# USB line inputs are asynchronous to usb48 and remain unconstrained; no false paths.
# Assumed integration budgets, not measured pad/board delays. ns and pF.
# Reset assertion asynchronous; release assumed 0.5..3 ns after usb48 edge.
# Recovery/removal stay enabled, so an inadequate release budget is a failure.
create_clock -name usb48 -period 20.833333 [get_ports clk_i]
set_clock_uncertainty -setup 0.5 [get_clocks usb48]
set_clock_uncertainty -hold 0.1 [get_clocks usb48]
set_clock_transition 0.2 [get_clocks usb48]
set sync_inputs [all_inputs -no_clocks]
set_input_delay -clock usb48 -max 3.0 $sync_inputs
set_input_delay -clock usb48 -min 0.5 $sync_inputs
unset_input_delay -clock usb48 -max [get_ports {usb_d_i usb_dp_i usb_dn_i}]
unset_input_delay -clock usb48 -min [get_ports {usb_d_i usb_dp_i usb_dn_i}]
set_input_transition 0.2 $sync_inputs
set_output_delay -clock usb48 -max 3.0 [all_outputs]
set_output_delay -clock usb48 -min 0.5 [all_outputs]
set_load 0.05 [all_outputs]
