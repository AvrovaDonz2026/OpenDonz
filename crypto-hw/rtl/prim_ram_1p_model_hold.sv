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
 localparam int MacroDepth=(Depth<=512)?512:1024;
 localparam int MacroAw=$clog2(MacroDepth);
 localparam int Banks=(Depth+MacroDepth-1)/MacroDepth, Lanes=(Width+7)/8;
 localparam int Bw=(Banks>1)?$clog2(Banks):1;
 logic [Bw-1:0] read_bank;
 logic [Banks-1:0][Lanes*8-1:0] q;
 wire [Lanes*8-1:0] wd={{(Lanes*8-Width){1'b0}},wdata_i};
 wire [Lanes*8-1:0] wm={{(Lanes*8-Width){1'b0}},wmask_i};
 wire [31:0] addr_ext=32'(addr_i);
 // The pinned model samples live write inputs 100 ps after CLK. Model-only
 // transport delay supplies that hold interval across zero-delay RTL updates.
 // No delay is present in synthesis; physical hold closure remains unproven.
 wire [31:0] macro_addr;
 wire [Lanes*8-1:0] macro_wd,macro_wm;
 wire macro_req,macro_write;
`ifdef GF180_SIM_HOLD
 assign #0.2ns macro_addr=addr_ext;
 assign #0.2ns macro_wd=wd;
 assign #0.2ns macro_wm=wm;
 assign #0.2ns macro_req=req_i;
 assign #0.2ns macro_write=write_i;
`else
 assign macro_addr=addr_ext;
 assign macro_wd=wd;
 assign macro_wm=wm;
 assign macro_req=req_i;
 assign macro_write=write_i;
`endif
 always_ff @(posedge clk_i) if(req_i && !write_i) read_bank <= Bw'(addr_ext >> MacroAw);
 for(genvar bank=0;bank<Banks;bank++) begin:g_bank
  for(genvar lane=0;lane<Lanes;lane++) begin:g_lane
   if(MacroDepth==512) begin:g_512
   gf180mcu_ocd_ip_sram__sram512x8m8wm1 u_macro(
    .CLK(clk_i),.CEN(!(macro_req && ((macro_addr >> MacroAw)==bank))),
    .GWEN(!macro_write),.WEN(~macro_wm[lane*8+:8]),.A(macro_addr[8:0]),
    .D(macro_wd[lane*8+:8]),.Q(q[bank][lane*8+:8]));
   end else begin:g_1024
   gf180mcu_ocd_ip_sram__sram1024x8m8wm1 u_macro(
    .CLK(clk_i),.CEN(!(macro_req && ((macro_addr >> MacroAw)==bank))),
    .GWEN(!macro_write),.WEN(~macro_wm[lane*8+:8]),.A(macro_addr[9:0]),
    .D(macro_wd[lane*8+:8]),.Q(q[bank][lane*8+:8]));
   end
  end
 end
 assign rdata_o=q[read_bank][Width-1:0];
 assign cfg_o=RAM_1P_CFG_RSP_DEFAULT;
 wire unused=^{rst_ni,cfg_i};
endmodule
