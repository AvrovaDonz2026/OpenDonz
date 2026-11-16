// Executable integration scaffold: inferred RAM and external trusted services.
// NVM response is supplied externally; this block is not persistent storage.
module soc_memory_mailbox # (parameter integer CLOCKS_PER_US = 48) (
 input logic clk_i, rst_ni,
 input logic instr_req_i, input logic [31:0] instr_addr_i,
 output logic instr_gnt_o, instr_rvalid_o, output logic [31:0] instr_rdata_o,
 input logic data_req_i, data_we_i, input logic [3:0] data_be_i,
 input logic [31:0] data_addr_i, data_wdata_i,
 output logic data_gnt_o, data_rvalid_o, data_err_o, output logic [31:0] data_rdata_o,
 input logic [511:0] hid_rx_i, input logic hid_rx_valid_i, output logic hid_rx_ready_o,
 output logic [511:0] hid_tx_o, output logic hid_tx_valid_o, input logic hid_tx_ready_i,
 input logic button_i, input logic rng_valid_i, input logic [7:0] rng_data_i,
 output logic rng_ready_o,
 output logic nvm_req_o, nvm_we_o, output logic [31:0] nvm_addr_o,
 output logic [7:0] nvm_wdata_o, output logic [2:0] nvm_command_o,
 input logic nvm_ready_i, nvm_error_i, input logic [31:0] nvm_rdata_i
);
 logic [31:0] ram [0:4095];
 logic [31:0] irom, drom, ticks, divider, nvm_address;
 logic [7:0] nvm_byte;
 logic button_meta, button_sync, button_latch;
 logic [511:0] rx_buffer, tx_buffer;
 logic rx_full, tx_full;
 logic [6:0] rx_index, tx_index;
 logic mmio, ram_hit, rom_hit, nvm_hit, accept;
 firmware_rom ir(.addr_i(instr_addr_i[14:2]),.data_o(irom));
 firmware_rom dr(.addr_i(data_addr_i[14:2]),.data_o(drom));
 assign mmio = data_addr_i[31:6] == (32'h40000000 >> 6);
 assign ram_hit = data_addr_i[31:14] == (32'h10000000 >> 14);
 assign rom_hit = data_addr_i < 32'h8000;
 assign nvm_hit = data_addr_i[31:12] == (32'h20000000 >> 12);
 assign nvm_req_o = data_req_i && (nvm_hit || (mmio && data_we_i && data_addr_i[5:0]==6'h34));
 assign nvm_we_o = data_we_i;
 assign nvm_addr_o = nvm_hit ? data_addr_i : nvm_address;
 assign nvm_wdata_o = nvm_byte;
 assign nvm_command_o = mmio ? data_wdata_i[2:0] : 3'b0;
 assign instr_gnt_o = instr_req_i;
 assign data_gnt_o = data_req_i && (!nvm_req_o || nvm_ready_i);
 assign accept = data_req_i && data_gnt_o;
 assign hid_rx_ready_o = !rx_full;
 assign hid_tx_valid_o = tx_full;
 assign hid_tx_o = tx_buffer;
 assign rng_ready_o = accept && !data_we_i && mmio && data_addr_i[5:0]==6'h24 && rng_valid_i;
 always_ff @(posedge clk_i or negedge rst_ni) begin
  if (!rst_ni) begin
   instr_rvalid_o<=0; instr_rdata_o<=0; data_rvalid_o<=0; data_rdata_o<=0; data_err_o<=0;
   ticks<=0; divider<=0; button_meta<=0; button_sync<=0; button_latch<=0;
   rx_full<=0; tx_full<=0; rx_index<=0; tx_index<=0;
   rx_buffer<=0; tx_buffer<=0; nvm_address<=0; nvm_byte<=0;
  end else begin
   button_meta<=button_i; button_sync<=button_meta;
   if (button_sync) button_latch<=1;
   if (divider == CLOCKS_PER_US-1) begin divider<=0; ticks<=ticks+1; end
   else divider<=divider+1;
   instr_rvalid_o<=instr_req_i;
   if(instr_req_i) instr_rdata_o<=instr_addr_i<32'h8000 ? irom : 32'b0;
   data_rvalid_o<=accept; data_err_o<=0;
   if (hid_rx_valid_i && hid_rx_ready_o) begin rx_buffer<=hid_rx_i; rx_full<=1; rx_index<=0; end
   if (hid_tx_valid_o && hid_tx_ready_i) begin tx_full<=0; tx_index<=0; end
   if(accept) begin
    data_rdata_o<=0;
    if(ram_hit) begin
     data_rdata_o<=ram[data_addr_i[13:2]];
     if(data_we_i) for(integer j=0;j<4;j=j+1) if(data_be_i[j]) ram[data_addr_i[13:2]][j*8+:8]<=data_wdata_i[j*8+:8];
    end else if(rom_hit && !data_we_i) data_rdata_o<=drom;
    else if(nvm_hit) begin data_rdata_o<=nvm_rdata_i; data_err_o<=nvm_error_i; end
    else if(mmio) begin
     case(data_addr_i[5:0])
      6'h00: data_rdata_o<={30'b0,!tx_full,rx_full};
      6'h04: if(!data_we_i && rx_full && rx_index<64) begin data_rdata_o<={24'b0,rx_buffer[rx_index[5:0]*8+:8]}; rx_index<=rx_index+1; end
      6'h08: if(data_we_i && !tx_full && tx_index<64) begin tx_buffer[tx_index[5:0]*8+:8]<=data_wdata_i[7:0]; tx_index<=tx_index+1; end
      6'h0c: if(data_we_i) begin
       if(data_wdata_i[0]) begin rx_full<=0; rx_index<=0; end
       if(data_wdata_i[1] && tx_index==64 && !tx_full) tx_full<=1;
      end
      6'h10: begin data_rdata_o<={31'b0,button_latch}; if(data_we_i && data_wdata_i[0]) button_latch<=0; end
      6'h18: data_rdata_o<=ticks;
      6'h20: data_rdata_o<={31'b0,rng_valid_i};
      6'h24: begin data_rdata_o<={24'b0,rng_data_i}; if(!rng_valid_i) data_err_o<=1; end
      6'h30: if(data_we_i) nvm_address<=data_wdata_i;
      6'h34: begin data_rdata_o<={30'b0,nvm_error_i,1'b0}; data_err_o<=nvm_error_i; end
      6'h38: if(data_we_i) nvm_byte<=data_wdata_i[7:0];
      6'h3c: data_rdata_o<=32'h55324631;
      default: data_err_o<=1;
     endcase
    end else data_err_o<=1;
   end
  end
 end
endmodule
