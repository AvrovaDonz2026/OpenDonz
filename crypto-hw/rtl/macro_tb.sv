`timescale 1ns/1ps
module macro_tb #(parameter Width=39, Depth=4096);
 localparam MacroDepth=(Depth<=512)?512:1024, Banks=(Depth+MacroDepth-1)/MacroDepth, Aw=$clog2(Depth);
 bit clk=0; always #25 clk=~clk;
 bit req=0,we=0; logic [Aw-1:0] a=0; logic [Width-1:0] d=0,m='1,q;
 prim_ram_1p #(.Width(Width),.Depth(Depth),.DataBitsPerMask(Width)) dut(
 .clk_i(clk),.rst_ni(1'b1),.req_i(req),.write_i(we),.addr_i(a),.wdata_i(d),.wmask_i(m),.rdata_o(q),.cfg_i('0),.cfg_o());
 task automatic store(input int addr,input logic[Width-1:0] val,input logic[Width-1:0] mask);
 @(negedge clk);req=1;we=1;a=Aw'(addr);d=val;m=mask;@(negedge clk);req=0;we=0;
 endtask
 task automatic check(input int addr,input logic[Width-1:0] val);
 @(negedge clk);req=1;we=0;a=Aw'(addr);@(negedge clk);req=0;
 if(q!==val) $fatal(1,"addr %0d q=%h expected=%h",addr,q,val);
 endtask
 initial begin
 #200; // Allow the foundry model delayed CEN initialization to settle.
 // Prime each bank with an idle/read transition required by the macro timing model.
 for(int bank=0;bank<Banks;bank++) begin
 @(negedge clk);req=1;we=0;a=Aw'(bank*MacroDepth);
 @(negedge clk);req=0;
 end
 for(int bank=0;bank<Banks;bank++) store(bank*MacroDepth+17,(Width'(bank+1) | (Width'(1) << (Width-1))),'1);
 for(int bank=Banks-1;bank>=0;bank--) check(bank*MacroDepth+17,(Width'(bank+1) | (Width'(1) << (Width-1))));
 store(17,'1,Width'('hff));check(17,Width'('hff) | (Width'(1) << (Width-1)));
 if(Banks>1) check(MacroDepth+17,Width'(2) | (Width'(1) << (Width-1)));
 store(Depth-1,'1,'1);check(Depth-1,'1);
 store(Depth-1,'0,Width'(1) << (Width-1));check(Depth-1,~(Width'(1) << (Width-1)));
 check(17,Width'('hff) | (Width'(1) << (Width-1)));
 $display("PASS macro synchronous read, bank selection, masked writes, non-clobber");$finish;
 end
endmodule
