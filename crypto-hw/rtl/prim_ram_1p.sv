// OpenDonz GF180 experiment: upstream prim_ram_1p interface, real OCD macros.
// SPDX-License-Identifier: Apache-2.0
module prim_ram_1p import prim_ram_1p_pkg::*; #(
 parameter int Width=32, Depth=128, DataBitsPerMask=1,
 parameter MemInitFile="", localparam int Aw=$clog2(Depth)
)(input logic clk_i,rst_ni,req_i,write_i,
 input logic [Aw-1:0] addr_i,
 input logic [Width-1:0] wdata_i,wmask_i,
 output logic [Width-1:0] rdata_o,
 input ram_1p_cfg_req_t cfg_i, output ram_1p_cfg_rsp_t cfg_o);
 localparam int Banks=(Depth+1023)/1024, Lanes=(Width+7)/8;
 localparam int Bw=(Banks>1)?$clog2(Banks):1;
 logic [Bw-1:0] read_bank;
 logic [Banks-1:0][Lanes*8-1:0] q;
 wire [Lanes*8-1:0] wd={{(Lanes*8-Width){1'b0}},wdata_i};
 wire [Lanes*8-1:0] wm={{(Lanes*8-Width){1'b0}},wmask_i};
 wire [31:0] addr_ext=32'(addr_i);
 always_ff @(posedge clk_i) if(req_i && !write_i) read_bank <= Bw'(addr_ext >> 10);
 for(genvar bank=0;bank<Banks;bank++) begin:g_bank
  for(genvar lane=0;lane<Lanes;lane++) begin:g_lane
   gf180mcu_ocd_ip_sram__sram1024x8m8wm1 u_macro(
    .CLK(clk_i),.CEN(!(req_i && ((addr_ext >> 10)==bank))),
    .GWEN(!write_i),.WEN(~wm[lane*8+:8]),.A(addr_ext[9:0]),
    .D(wd[lane*8+:8]),.Q(q[bank][lane*8+:8]));
  end
 end
 assign rdata_o=q[read_bank][Width-1:0];
 assign cfg_o=RAM_1P_CFG_RSP_DEFAULT;
 wire unused=^{rst_ni,cfg_i};
endmodule
