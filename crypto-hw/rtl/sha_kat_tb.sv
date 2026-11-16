`timescale 1ns/1ps
module sha_kat_tb;
 import prim_sha2_pkg::*;
 bit clk=0; always #5 clk=~clk;
 bit rst=0,start=0,process_msg=0,valid=0,wipe=0;
 sha_fifo32_t din; wire ready,done;sha_word64_t [7:0] digest;
 prim_sha2_32 #(.MultimodeEn(1)) dut(.clk_i(clk),.rst_ni(rst),.wipe_secret_i(wipe),.wipe_v_i(32'h0),
 .fifo_rvalid_i(valid),.fifo_rdata_i(din),.fifo_rready_o(ready),.sha_en_i(1'b1),
 .hash_start_i(start),.hash_stop_i(1'b0),.hash_continue_i(1'b0),.digest_mode_i(SHA2_256),
 .hash_process_i(process_msg),.hash_done_o(done),.message_length_i(64'd24),
 .digest_i('0),.digest_we_i('0),.digest_o(digest),.digest_on_blk_o(),.hash_running_o(),.idle_o());
 initial begin
 repeat(4) @(negedge clk);rst=1;@(negedge clk);start=1;@(negedge clk);start=0;
 din.data=32'h61626300;din.mask=4'b1110;valid=1;
 do @(posedge clk); while(!ready);
 @(negedge clk);valid=0;process_msg=1;@(negedge clk);process_msg=0;
 wait(done);repeat(3) @(negedge clk);
 if({digest[0][31:0],digest[1][31:0],digest[2][31:0],digest[3][31:0],digest[4][31:0],digest[5][31:0],digest[6][31:0],digest[7][31:0]}!==256'hba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad)
 $fatal(1,"SHA256 abc mismatch %h",digest);
 wipe=1;repeat(3) @(negedge clk);wipe=0;
 if(digest!=='0)$fatal(1,"digest wipe failed");
 $display("PASS upstream SHA256 abc KAT and digest wipe; primitive RTL only");$finish;
 end
 initial begin #100000;$fatal(1,"timeout");end
endmodule
