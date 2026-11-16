// Two-endpoint development bridge. SET_ADDRESS/CONFIGURATION apply after status ACK.
module usb_u2f_bridge(
 input logic clk_i, rst_ni, link_reset_i,
 output logic [6:0] dev_addr_o,
 input logic [3:0] out_ep_current_i, input logic out_ep_newpkt_i, out_ep_data_put_i,
 input logic [7:0] out_ep_data_i,
 input logic out_ep_acked_i, input logic [1:0] out_ep_setup_i,
 output logic [1:0] out_ep_full_o, out_ep_stall_o,
 input logic [3:0] in_ep_current_i, input logic [5:0] in_ep_get_addr_i,
 input logic in_ep_data_get_i, in_ep_newpkt_i, in_ep_xact_end_i,
 output logic [1:0] in_ep_has_data_o, in_ep_data_done_o, in_ep_stall_o,
 output logic [7:0] in_ep_data_o,
 output logic [511:0] hid_rx_o, output logic hid_rx_valid_o, input logic hid_rx_ready_i,
 input logic [511:0] hid_tx_i, input logic hid_tx_valid_i, output logic hid_tx_ready_o
);
 localparam logic [8*18-1:0] DEVICE = 144'h010000000100000000004000000002000112;
 // PID/VID 0000 are development placeholders, not an assigned USB identity.
 localparam logic [8*41-1:0] CONFIG = 328'h0100400381050701004003010507002222010001112109000000030200000409328000010100290209;
 localparam logic [8*34-1:0] REPORT = 272'hc002914095087500ff260015210902814095087500ff260015200901a10109f1d006;
 logic [7:0] packet[0:65]; logic [6:0] received_count;
 logic [7:0] source_kind;
 logic [6:0] ctrl_length, read_count, ep1_read_count;
 logic ctrl_pending, stalled, configured, status_pending, set_address, set_config;
 logic [6:0] pending_address; logic pending_config;
 logic [511:0] ep1_tx;
 logic ep1_pending;
 logic [7:0] request_type, request;
 logic [15:0] value, length_value;
 assign request_type=packet[0]; assign request=packet[1];
 assign value={packet[3],packet[2]}; assign length_value={packet[7],packet[6]};
 assign in_ep_has_data_o={ep1_pending && configured,ctrl_pending};
 assign out_ep_full_o={!configured || hid_rx_valid_o,1'b0};
 assign out_ep_stall_o={1'b0,stalled}; assign in_ep_stall_o={1'b0,stalled};
 assign in_ep_data_done_o={ep1_read_count>=64,read_count>=ctrl_length};
 assign hid_tx_ready_o=configured && !ep1_pending;
 always_comb begin
  in_ep_data_o=0;
  if(in_ep_current_i==1) in_ep_data_o=ep1_tx[in_ep_get_addr_i*8+:8];
  else case(source_kind)
   1: if(in_ep_get_addr_i<18) in_ep_data_o=DEVICE[(in_ep_get_addr_i)*8+:8];
   2: if(in_ep_get_addr_i<41) in_ep_data_o=CONFIG[(in_ep_get_addr_i)*8+:8];
   3: if(in_ep_get_addr_i<34) in_ep_data_o=REPORT[(in_ep_get_addr_i)*8+:8];
   4: if(in_ep_get_addr_i==0) in_ep_data_o={7'b0,configured};
   default: in_ep_data_o=0;
  endcase
 end
 always_ff @(posedge clk_i or negedge rst_ni) begin
  if(!rst_ni) begin
   dev_addr_o<=0; configured<=0; ctrl_pending<=0; stalled<=0; status_pending<=0;
   set_address<=0; set_config<=0; pending_address<=0; pending_config<=0;
   hid_rx_o<=0; hid_rx_valid_o<=0; ep1_pending<=0; ep1_tx<=0;
   received_count<=0; ctrl_length<=0; read_count<=0; ep1_read_count<=0;
   source_kind<=0;
  end else if(link_reset_i) begin
   dev_addr_o<=0; configured<=0; ctrl_pending<=0; stalled<=0; status_pending<=0;
   hid_rx_valid_o<=0; ep1_pending<=0; set_address<=0; set_config<=0;
   read_count<=0; ep1_read_count<=0; received_count<=0;
  end else begin
   if(hid_rx_valid_o && hid_rx_ready_i) hid_rx_valid_o<=0;
   if(hid_tx_valid_i && hid_tx_ready_o) begin ep1_tx<=hid_tx_i; ep1_pending<=1; end
   if(out_ep_newpkt_i) received_count<=0;
   if(out_ep_data_put_i) begin
    if(received_count<66) packet[received_count]<=out_ep_data_i;
    if(received_count<66) received_count<=received_count+1;
   end
   if(out_ep_acked_i && out_ep_current_i==1 && received_count==66) begin
    for(integer j=0;j<64;j=j+1) hid_rx_o[j*8+:8]<=packet[j];
    hid_rx_valid_o<=1;
   end
   if(out_ep_acked_i && out_ep_current_i==0 && out_ep_setup_i[0]) begin
    ctrl_pending<=0; stalled<=0; set_address<=0; set_config<=0; status_pending<=0;
    read_count<=0;
    if(received_count!=10) stalled<=1;
    else if(request==6 && request_type[7]) begin
     case(value[15:8])
      1: begin source_kind<=1; ctrl_length<=length_value<18 ? 7'(length_value) : 18; ctrl_pending<=1; end
      2: begin source_kind<=2; ctrl_length<=length_value<41 ? 7'(length_value) : 41; ctrl_pending<=1; end
      8'h22: begin source_kind<=3; ctrl_length<=length_value<34 ? 7'(length_value) : 34; ctrl_pending<=1; end
      default: stalled<=1;
     endcase
    end else if(request==5 && request_type==0 && length_value==0 && value<128) begin
     set_address<=1; pending_address<=value[6:0]; status_pending<=1; ctrl_pending<=1; ctrl_length<=0;
    end else if(request==9 && request_type==0 && length_value==0 && value<=1) begin
     set_config<=1; pending_config<=value[0]; status_pending<=1; ctrl_pending<=1; ctrl_length<=0;
    end else if(request==8 && request_type==8'h80 && length_value==1) begin source_kind<=4; ctrl_length<=1; ctrl_pending<=1; end
    else if(request==0 && request_type[7] && length_value==2) begin source_kind<=0; ctrl_length<=2; ctrl_pending<=1; end
    else if(request==8'h0a && request_type==8'h21 && length_value==0) begin status_pending<=1; ctrl_pending<=1; ctrl_length<=0; end
    else stalled<=1;
   end
   if(in_ep_newpkt_i) begin
    if(in_ep_current_i==0) read_count<=0; else ep1_read_count<=0;
   end
   if(in_ep_data_get_i) begin
    if(in_ep_current_i==0) read_count<=read_count+1; else ep1_read_count<=ep1_read_count+1;
   end
   if(in_ep_xact_end_i) begin
    if(in_ep_current_i==1) ep1_pending<=0;
    else begin
     ctrl_pending<=0;
     if(status_pending) begin
      if(set_address) dev_addr_o<=pending_address;
      if(set_config) configured<=pending_config;
      status_pending<=0; set_address<=0; set_config<=0;
     end
    end
   end
  end
 end
endmodule
