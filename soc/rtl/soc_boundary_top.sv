// Measurement boundary only: external memory, debug transport and endpoint controller required.
module soc_boundary_top (
  output logic instr_req_o, output logic [31:0] instr_addr_o,
  input logic instr_gnt_i, instr_rvalid_i, input logic [31:0] instr_rdata_i,
  output logic data_req_o, data_we_o, output logic [3:0] data_be_o,
  output logic [31:0] data_addr_o, data_wdata_o,
  input logic data_gnt_i, data_rvalid_i, input logic [31:0] data_rdata_i,
  input logic debug_req_i,

  input  logic                   clk_i,
  input  logic                   rst_ni,        // Async. reset, active low
  input  logic                   link_reset_i,  // USB reset, sync to 48 MHz, active high
  input  logic                   link_active_i, // Device is in Default/Addressed/Configured state
                                                // and may respond to transactions
  input  logic [6:0]             dev_addr_i,

  input  logic                   cfg_eop_single_bit_i, // 1: detect a single SE0 bit as EOP
  input  logic                   cfg_use_diff_rcvr_i, // 1: use usb_d_i from a differential receiver
  input  logic                   cfg_pinflip_i, // 1: USB-side D+ and D- pins are flipped.
                                                // Change values in logic to accommodate.
  input  logic                   tx_osc_test_mode_i, // Oscillator test mode (constantly output JK)
  output logic [2-1:0]   out_data_toggle_o, // Current state of OUT data toggles
  input  logic                   out_datatog_we_i, // OUT data toggles write strobe from software
  input  logic [2-1:0]   out_datatog_status_i, // New state of selected OUT data toggles
  input  logic [2-1:0]   out_datatog_mask_i, // Which OUT EP data toggles to modify
  output logic [2-1:0]    in_data_toggle_o, // Current state of IN data toggles
  input  logic                   in_datatog_we_i, // IN data toggles write strobe from software
  input  logic [2-1:0]    in_datatog_status_i, // New state of selected IN data toggles
  input  logic [2-1:0]    in_datatog_mask_i, // Which IN EP data toggles to modify
  input  logic                   diff_rx_ok_i, // 1: received differential data symbols are valid.
                                               // Set low if K and J symbols might be invalid, such
                                               // as when an external differential receiver is
                                               // powering on.

  ////////////////////////////
  // USB Endpoint Interface //
  ////////////////////////////
  ///////////////////////////////
  // global endpoint interface //
  ///////////////////////////////

  // out endpoint interfaces
  output logic [3:0]             out_ep_current_o, // Other signals address to this ep
  output logic                   out_ep_data_put_o, // put the data (put addr advances after)
  output logic [5:0]      out_ep_put_addr_o, // Offset to put data (0..pktlen)
  output logic [7:0]             out_ep_data_o,
  output logic                   out_ep_newpkt_o,// New OUT pkt start (with in_ep_current_o update)
  output logic                   out_ep_acked_o, // good termination, device has acked
  output logic                   out_ep_rollback_o, // bad termination, discard data
  output logic [2-1:0]   out_ep_setup_o,
  input  logic [2-1:0]   out_ep_enabled_i, // Endpoint is enabled and produces handshakes
  input  logic [2-1:0]   out_ep_control_i, // Is a control endpoint: Accepts SETUP packets
  input  logic [2-1:0]   out_ep_full_i, // Cannot accept data
  input  logic [2-1:0]   out_ep_stall_i, // Stalled
  input  logic [2-1:0]   out_ep_iso_i, // Configure endpoint in isochronous mode

  // in endpoint interfaces
  output logic                   in_xact_starting_o, // Start of an IN transaction
  output logic [3:0]             in_xact_start_ep_o, // Capture IN packet details

  output logic [3:0]             in_ep_current_o, // Other signals addressed to this ep
  output logic                   in_ep_rollback_o, // Bad termination, rollback transaction
  output logic                   in_ep_xact_end_o, // good termination, transaction complete
  output logic [5:0]      in_ep_get_addr_o, // Offset requested (0..pktlen)
  output logic                   in_ep_data_get_o, // Accept data (get_addr advances too)
  output logic                   in_ep_newpkt_o, // New IN pkt start (with in_ep_current_o update)
  input  logic [2-1:0]    in_ep_enabled_i, // Endpoint is enabled and produces handshakes
  input  logic [2-1:0]    in_ep_stall_i, // Endpoint in a stall state
  input  logic [2-1:0]    in_ep_has_data_i, // Endpoint has data to supply
  input  logic [7:0]             in_ep_data_i, // Data for current get_addr
  input  logic [2-1:0]    in_ep_data_done_i, // Set when out of data
  input  logic  [2-1:0]   in_ep_iso_i, // Configure endpoint in isochronous mode

  // sof interface
  output logic                   sof_detected_o, // SOF detected, PID valid
  output logic                   sof_valid_o, // SOF packet valid; frame number may be trusted
  output logic [10:0]            frame_index_o,

  // RX line status
  output logic                   rx_idle_det_o,
  output logic                   rx_j_det_o,

  // RX errors
  output logic                   rx_crc5_err_o,
  output logic                   rx_crc16_err_o,
  output logic                   rx_pid_err_o,
  output logic                   rx_bitstuff_err_o,

  ///////////////////////////////////////
  // USB RX Interface (synchronous)    //
  ///////////////////////////////////////
  input  logic                   usb_d_i,
  input  logic                   usb_dp_i,
  input  logic                   usb_dn_i,

  ///////////////////////////////////////
  // USB TX Interface (synchronous)    //
  ///////////////////////////////////////
  output logic                   usb_d_o,
  output logic                   usb_se0_o,
  output logic                   usb_dp_o,
  output logic                   usb_dn_o,
  output logic                   usb_oe_o,

  // event counters
  output logic                   event_datatog_out_o,
  output logic                   event_timeout_in_o,
  output logic                   event_nak_in_o,
  output logic                   event_nodata_in_o
);

  ibex_top #(.RV32M(ibex_pkg::RV32MFast), .RV32B(ibex_pkg::RV32BNone),
    .RV32ZC(ibex_pkg::RV32Zca), .ICache(0), .SecureIbex(0)) cpu (
    .clk_i, .rst_ni, .test_en_i(1'b0), .scan_rst_ni(1'b1),
    .hart_id_i(32'b0), .boot_addr_i(32'b0),
    .cheriot_enable_i(ibex_pkg::IbexMuBiOff), .trvk_heap_base_addr_i(32'b0),
    .ram_cfg_icache_tag_i('0), .ram_cfg_icache_data_i('0),
    .instr_req_o, .instr_addr_o, .instr_gnt_i, .instr_rvalid_i, .instr_rdata_i,
    .instr_rdata_intg_i('0), .instr_err_i(1'b0),
    .data_req_o, .data_we_o, .data_be_o, .data_addr_o, .data_wdata_o,
    .data_gnt_i, .data_rvalid_i, .data_rdata_i, .data_rdata_intg_i('0),
    .data_tag_i(1'b0), .data_err_i(1'b0),
    .trvk_revbm_gnt_i(1'b0), .trvk_revbm_rvalid_i(1'b0),
    .trvk_revbm_rdata_i('0), .trvk_revbm_rdata_intg_i('0), .trvk_revbm_err_i(1'b0),
    .irq_software_i(1'b0), .irq_timer_i(1'b0), .irq_external_i(1'b0),
    .irq_fast_i('0), .irq_nm_i(1'b0), .debug_req_i,
    .scramble_key_valid_i(1'b0), .scramble_key_i('0), .scramble_nonce_i('0),
    .fetch_enable_i(ibex_pkg::IbexMuBiOn), .mcounteren_writable_i(ibex_pkg::IbexMuBiOff)
  );

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
