// P0: expose the complete PE boundary; no endpoint or active-link constant folding.
module usb_fs_nb_pe_top (
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
  // Async assertion, two rising-edge release stages. Hold traffic until the
  // third rising edge after rst_ni rises. Recovery/removal remain STA checked,
  // including both synchronizer flops; synchronization is not a timing waiver.
  (* async_reg = "true" *) logic [1:0] reset_release_q;
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) reset_release_q <= '0;
    else reset_release_q <= {reset_release_q[0], 1'b1};
  end

  usb_fs_nb_pe #(.NumOutEps(2), .NumInEps(2), .MaxPktSizeByte(64)) dut (
    .clk_48mhz_i(clk_i),
    .rst_ni(reset_release_q[1]),
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
