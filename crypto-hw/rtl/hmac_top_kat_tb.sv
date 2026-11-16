`timescale 1ns/1ps
module hmac_top_kat_tb;
 import tlul_pkg::*;
 bit clk=0;always #5 clk=~clk;
 bit rst=0;tl_h2d_t ti=TL_H2D_DEFAULT;tl_d2h_t to;
 logic done,empty,err;
 hmac dut(.clk_i(clk),.rst_ni(rst),.tl_i(ti),.tl_o(to),.alert_rx_i('0),.alert_tx_o(),.keymgr_key_i('0),.intr_hmac_done_o(done),.intr_fifo_empty_o(empty),.intr_hmac_err_o(err),.idle_o());
 task automatic bus(input bit wr,input int addr,input int val,output int result);
 @(negedge clk);ti=TL_H2D_DEFAULT;ti.a_valid=1;ti.a_opcode=wr?PutFullData:Get;
 ti.a_size=2;ti.a_mask=15;ti.a_address=addr;ti.a_data=val;
 ti.a_user.cmd_intg=get_cmd_intg(ti);ti.a_user.data_intg=get_data_intg(ti.a_data);
 do @(posedge clk);while(!to.a_ready);
 @(negedge clk);ti.a_valid=0;
 while(!to.d_valid) @(negedge clk);
 if(to.d_error)$fatal(1,"TL error at %h",addr);
 if(to.d_user.rsp_intg!==get_rsp_intg(to) || to.d_user.data_intg!==get_data_intg(to.d_data))$fatal(1,"TL response integrity");
 result=to.d_data;@(negedge clk);
 endtask
 task automatic wr(input int a,input int v);int q;bus(1,a,v,q);endtask
 task automatic run(input bit keyed,input string msg,input logic[255:0] expected);
 int q;int wordval;
 rst=0;repeat(5)@(negedge clk);rst=1;repeat(5)@(negedge clk);
 wr('h4,1);wr('h10,'h422|int'(keyed));
 if(keyed)for(int i=0;i<8;i++)wr('h24+4*i,i<5?'h0b0b0b0b:0);
 wr('h14,1);
 // Byte writes exercise FIFO masks, including non-word-aligned messages.
 for(int i=0;i<msg.len();i++)begin
 @(negedge clk);ti=TL_H2D_DEFAULT;ti.a_valid=1;ti.a_opcode=PutPartialData;ti.a_size=0;ti.a_mask=1;ti.a_address='h1000;ti.a_data=int'(msg.getc(i));
 ti.a_user.cmd_intg=get_cmd_intg(ti);ti.a_user.data_intg=get_data_intg(ti.a_data);
 do @(posedge clk);while(!to.a_ready);
 @(negedge clk);ti.a_valid=0;while(!to.d_valid)@(negedge clk);if(to.d_error)$fatal(1,"FIFO TL error");@(negedge clk);
 end
 wr('h14,2);
 for(int n=0;n<20000;n++)begin
 bus(0,0,0,q);if(q&1)break;if(n==19999)$fatal(1,"hash timeout err=%b",err);
 end
 if(!done || err)$fatal(1,"interrupt status done=%b err=%b",done,err);
 for(int i=0;i<8;i++)begin bus(0,'ha4+4*i,0,q);if(q!==expected[255-32*i-:32])$fatal(1,"digest word %0d %h expected %h",i,q,expected[255-32*i-:32]);end
 $display("PASS HMAC top TLUL/register/FIFO keyed=%b len=%0d",keyed,msg.len());
 endtask
 initial begin
 run(0,"",256'he3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855);
 run(0,"abc",256'hba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad);
 run(1,"Hi There",256'hb0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7);
 $finish;end
 initial begin #10000000;$fatal(1,"global timeout");end
endmodule
