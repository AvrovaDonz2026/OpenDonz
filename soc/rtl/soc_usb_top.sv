module soc_usb_top(
 input logic clk_i, rst_ni, link_reset_i, usb_d_i, usb_dp_i, usb_dn_i,
 input logic rng_valid_i, input logic [7:0] rng_data_i, output logic rng_ready_o,
 output logic usb_d_o, usb_se0_o, usb_dp_o, usb_dn_o, usb_oe_o
);
 logic  link_active_i;
 logic [6:0] dev_addr_i;
 logic  cfg_eop_single_bit_i;
 logic  cfg_use_diff_rcvr_i;
 logic  cfg_pinflip_i;
 logic  tx_osc_test_mode_i;
 logic [2-1:0] out_data_toggle_o;
 logic  out_datatog_we_i;
 logic [2-1:0] out_datatog_status_i;
 logic [2-1:0] out_datatog_mask_i;
 logic [2-1:0] in_data_toggle_o;
 logic  in_datatog_we_i;
 logic [2-1:0] in_datatog_status_i;
 logic [2-1:0] in_datatog_mask_i;
 logic  diff_rx_ok_i;
 logic [3:0] out_ep_current_o;
 logic  out_ep_data_put_o;
 logic [5:0] out_ep_put_addr_o;
 logic [7:0] out_ep_data_o;
 logic  out_ep_newpkt_o;
 logic  out_ep_acked_o;
 logic  out_ep_rollback_o;
 logic [2-1:0] out_ep_setup_o;
 logic [2-1:0] out_ep_enabled_i;
 logic [2-1:0] out_ep_control_i;
 logic [2-1:0] out_ep_full_i;
 logic [2-1:0] out_ep_stall_i;
 logic [2-1:0] out_ep_iso_i;
 logic  in_xact_starting_o;
 logic [3:0] in_xact_start_ep_o;
 logic [3:0] in_ep_current_o;
 logic  in_ep_rollback_o;
 logic  in_ep_xact_end_o;
 logic [5:0] in_ep_get_addr_o;
 logic  in_ep_data_get_o;
 logic  in_ep_newpkt_o;
 logic [2-1:0] in_ep_enabled_i;
 logic [2-1:0] in_ep_stall_i;
 logic [2-1:0] in_ep_has_data_i;
 logic [7:0] in_ep_data_i;
 logic [2-1:0] in_ep_data_done_i;
 logic [2-1:0] in_ep_iso_i;
 logic  sof_detected_o;
 logic  sof_valid_o;
 logic [10:0] frame_index_o;
 logic  rx_idle_det_o;
 logic  rx_j_det_o;
 logic  rx_crc5_err_o;
 logic  rx_crc16_err_o;
 logic  rx_pid_err_o;
 logic  rx_bitstuff_err_o;
 logic  event_datatog_out_o;
 logic  event_timeout_in_o;
 logic  event_nak_in_o;
 logic  event_nodata_in_o;
 logic [511:0] hid_rx, hid_tx; logic rx_valid, rx_ready, tx_valid, tx_ready;
 logic nvm_req, nvm_we; logic [31:0] nvm_addr; logic [7:0] nvm_byte; logic [2:0] nvm_command;
 assign link_active_i=1'b1; assign cfg_eop_single_bit_i=0; assign cfg_use_diff_rcvr_i=0;
 assign cfg_pinflip_i=0; assign tx_osc_test_mode_i=0; assign diff_rx_ok_i=1;
 assign out_datatog_we_i=0; assign out_datatog_status_i=0; assign out_datatog_mask_i=0;
 assign in_datatog_we_i=0; assign in_datatog_status_i=0; assign in_datatog_mask_i=0;
 assign out_ep_enabled_i=3; assign out_ep_control_i=1; assign out_ep_iso_i=0;
 assign in_ep_enabled_i=3; assign in_ep_iso_i=0;
 // External entropy interface; NVM is erased reads / acknowledged-discarded writes (NONPERSISTENT TEST STUB).
 soc_firmware_top cpu(.clk_i,.rst_ni,.debug_req_i(1'b0),
 .hid_rx_i(hid_rx),.hid_rx_valid_i(rx_valid),.hid_rx_ready_o(rx_ready),
 .hid_tx_o(hid_tx),.hid_tx_valid_o(tx_valid),.hid_tx_ready_i(tx_ready),
 .button_i(1'b0),.rng_valid_i,.rng_data_i,.rng_ready_o,
 .nvm_req_o(nvm_req),.nvm_we_o(nvm_we),.nvm_addr_o(nvm_addr),.nvm_wdata_o(nvm_byte),.nvm_command_o(nvm_command),
 .nvm_ready_i(1'b1),.nvm_error_i(1'b0),.nvm_rdata_i(32'hffffffff));
 usb_u2f_bridge bridge(.clk_i,.rst_ni,.link_reset_i,.dev_addr_o(dev_addr_i),
 .out_ep_current_i(out_ep_current_o),.out_ep_newpkt_i(out_ep_newpkt_o),.out_ep_data_put_i(out_ep_data_put_o),
 .out_ep_data_i(out_ep_data_o),.out_ep_acked_i(out_ep_acked_o),
 .out_ep_setup_i(out_ep_setup_o),
 .out_ep_full_o(out_ep_full_i),.out_ep_stall_o(out_ep_stall_i),
 .in_ep_current_i(in_ep_current_o),.in_ep_get_addr_i(in_ep_get_addr_o),.in_ep_data_get_i(in_ep_data_get_o),
 .in_ep_newpkt_i(in_ep_newpkt_o),.in_ep_xact_end_i(in_ep_xact_end_o),
 .in_ep_has_data_o(in_ep_has_data_i),.in_ep_data_done_o(in_ep_data_done_i),.in_ep_stall_o(in_ep_stall_i),.in_ep_data_o(in_ep_data_i),
 .hid_rx_o(hid_rx),.hid_rx_valid_o(rx_valid),.hid_rx_ready_i(rx_ready),
 .hid_tx_i(hid_tx),.hid_tx_valid_i(tx_valid),.hid_tx_ready_o(tx_ready));
usb_fs_nb_pe_top usb (
 .clk_i(clk_i),
 .rst_ni(rst_ni),
 .link_reset_i(link_reset_i),
 .link_active_i(link_active_i),
 .dev_addr_i(dev_addr_i),
 .cfg_eop_single_bit_i(cfg_eop_single_bit_i),
 .cfg_use_diff_rcvr_i(cfg_use_diff_rcvr_i),
 .cfg_pinflip_i(cfg_pinflip_i),
 .tx_osc_test_mode_i(tx_osc_test_mode_i),
 .out_data_toggle_o(out_data_toggle_o),
 .out_datatog_we_i(out_datatog_we_i),
 .out_datatog_status_i(out_datatog_status_i),
 .out_datatog_mask_i(out_datatog_mask_i),
 .in_data_toggle_o(in_data_toggle_o),
 .in_datatog_we_i(in_datatog_we_i),
 .in_datatog_status_i(in_datatog_status_i),
 .in_datatog_mask_i(in_datatog_mask_i),
 .diff_rx_ok_i(diff_rx_ok_i),
 .out_ep_current_o(out_ep_current_o),
 .out_ep_data_put_o(out_ep_data_put_o),
 .out_ep_put_addr_o(out_ep_put_addr_o),
 .out_ep_data_o(out_ep_data_o),
 .out_ep_newpkt_o(out_ep_newpkt_o),
 .out_ep_acked_o(out_ep_acked_o),
 .out_ep_rollback_o(out_ep_rollback_o),
 .out_ep_setup_o(out_ep_setup_o),
 .out_ep_enabled_i(out_ep_enabled_i),
 .out_ep_control_i(out_ep_control_i),
 .out_ep_full_i(out_ep_full_i),
 .out_ep_stall_i(out_ep_stall_i),
 .out_ep_iso_i(out_ep_iso_i),
 .in_xact_starting_o(in_xact_starting_o),
 .in_xact_start_ep_o(in_xact_start_ep_o),
 .in_ep_current_o(in_ep_current_o),
 .in_ep_rollback_o(in_ep_rollback_o),
 .in_ep_xact_end_o(in_ep_xact_end_o),
 .in_ep_get_addr_o(in_ep_get_addr_o),
 .in_ep_data_get_o(in_ep_data_get_o),
 .in_ep_newpkt_o(in_ep_newpkt_o),
 .in_ep_enabled_i(in_ep_enabled_i),
 .in_ep_stall_i(in_ep_stall_i),
 .in_ep_has_data_i(in_ep_has_data_i),
 .in_ep_data_i(in_ep_data_i),
 .in_ep_data_done_i(in_ep_data_done_i),
 .in_ep_iso_i(in_ep_iso_i),
 .sof_detected_o(sof_detected_o),
 .sof_valid_o(sof_valid_o),
 .frame_index_o(frame_index_o),
 .rx_idle_det_o(rx_idle_det_o),
 .rx_j_det_o(rx_j_det_o),
 .rx_crc5_err_o(rx_crc5_err_o),
 .rx_crc16_err_o(rx_crc16_err_o),
 .rx_pid_err_o(rx_pid_err_o),
 .rx_bitstuff_err_o(rx_bitstuff_err_o),
 .usb_d_i(usb_d_i),
 .usb_dp_i(usb_dp_i),
 .usb_dn_i(usb_dn_i),
 .usb_d_o(usb_d_o),
 .usb_se0_o(usb_se0_o),
 .usb_dp_o(usb_dp_o),
 .usb_dn_o(usb_dn_o),
 .usb_oe_o(usb_oe_o),
 .event_datatog_out_o(event_datatog_out_o),
 .event_timeout_in_o(event_timeout_in_o),
 .event_nak_in_o(event_nak_in_o),
 .event_nodata_in_o(event_nodata_in_o)
);
endmodule
