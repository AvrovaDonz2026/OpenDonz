module tb_firmware;
 logic clk=0; always #5 clk=~clk;
 logic rst=0;
 logic [511:0] rx, tx;
 logic rx_valid, rx_ready, tx_valid, tx_ready;
 logic nvm_req, nvm_we, rng_ready; logic [31:0] nvm_addr; logic [7:0] nvm_data; logic [2:0] nvm_command;
 soc_firmware_top dut(.clk_i(clk),.rst_ni(rst),.debug_req_i(1'b0),
 .hid_rx_i(rx),.hid_rx_valid_i(rx_valid),.hid_rx_ready_o(rx_ready),
 .hid_tx_o(tx),.hid_tx_valid_o(tx_valid),.hid_tx_ready_i(tx_ready),
 .button_i(1'b0),.rng_valid_i(1'b1),.rng_data_i(8'h1),.rng_ready_o(rng_ready),
 .nvm_req_o(nvm_req),.nvm_we_o(nvm_we),.nvm_addr_o(nvm_addr),.nvm_wdata_o(nvm_data),.nvm_command_o(nvm_command),
 .nvm_ready_i(1'b1),.nvm_error_i(1'b0),.nvm_rdata_i(32'hffffffff));
 task send_report(input logic [511:0] report);
  @(negedge clk); rx=report; rx_valid=1;
  do @(posedge clk); while(!rx_ready);
  @(negedge clk); rx_valid=0;
 endtask
 task receive_report;
  wait(tx_valid); @(negedge clk);
 endtask
 logic [511:0] report;
 logic [31:0] cid;
 initial begin
  rx=0; rx_valid=0; tx_ready=0;
  repeat(8) @(negedge clk); rst=1;
  // Broadcast INIT, 8-byte nonce.
  report=0; report[31:0]=32'hffffffff; report[39:32]=8'h86; report[55:48]=8;
  report[119:56]=64'h8877665544332211;
  send_report(report); receive_report();
  if(tx[39:32]!=8'h86 || tx[55:48]!=17 || tx[119:56]!=report[119:56]) $fatal(1,"INIT response mismatch");
  cid=tx[151:120];
  tx_ready=1; @(negedge clk); tx_ready=0;
  // U2FHID_MSG containing U2F_VERSION extended APDU.
  report=0; report[31:0]=cid; report[39:32]=8'h83; report[55:48]=7;
  report[111:56]=56'h00000000000300;
  send_report(report); receive_report();
  if(tx[39:32]!=8'h83 || tx[55:48]!=8 || tx[119:56]!=64'h009032565f463255) $fatal(1,"VERSION response mismatch: %h",tx);
  $display("PASS actual Ibex reset -> startup -> HID INIT -> U2F_VERSION mailbox path");
  $finish;
 end
 initial begin repeat(1000000) @(posedge clk); $fatal(1,"firmware integration timeout pc=%h",dut.instr_addr_o); end
endmodule
