`timescale 1ns/1ps
module otbn_full_tb;
 import tlul_pkg::*;import otbn_pkg::*;
 bit clk=0;always #5 clk=~clk;
 bit rst=0;tl_h2d_t ti=TL_H2D_DEFAULT;tl_d2h_t to;
 edn_pkg::edn_req_t rnd_req,urnd_req;edn_pkg::edn_rsp_t rnd_rsp,urnd_rsp;
 otp_ctrl_pkg::otbn_otp_key_req_t otp_req;otp_ctrl_pkg::otbn_otp_key_rsp_t otp_rsp;
 int entropy_count=0;int otp_count=0;logic [31:0] rng=32'hf17482ac;
 // Functional external EDN provider only: deterministic PRNG is NOT a qualified entropy source.
 always @(posedge clk)begin
 rng<={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
 rnd_rsp.edn_ack<=rst && rnd_req.edn_req && !rnd_rsp.edn_ack;
 urnd_rsp.edn_ack<=rst && urnd_req.edn_req && !urnd_rsp.edn_ack;
 rnd_rsp.edn_bus<=rng;rnd_rsp.edn_fips<=1;urnd_rsp.edn_bus<=rng^32'ha59fc873;urnd_rsp.edn_fips<=1;
 if(urnd_rsp.edn_ack)entropy_count<=entropy_count+1;
 otp_rsp.ack<=rst && otp_req.req && !otp_rsp.ack;
 if(otp_rsp.ack)otp_count<=otp_count+1;
 end
 assign otp_rsp.key=128'h13579bdf2468ace087654321fedcba98 ^ 128'(otp_count);
 assign otp_rsp.nonce=256'h112233445566778899aabbccddeeff00;
 assign otp_rsp.seed_valid=1;
 otbn dut(.clk_i(clk),.rst_ni(rst),.tl_i(ti),.tl_o(to),.idle_o(),.intr_done_o(),
 .alert_rx_i('0),.alert_tx_o(),.lc_escalate_en_i(lc_ctrl_pkg::Off),.lc_rma_req_i(lc_ctrl_pkg::Off),.lc_rma_ack_o(),
 .ram_cfg_imem_i('0),.ram_cfg_dmem_i('0),.ram_cfg_imem_o(),.ram_cfg_dmem_o(),
 .clk_edn_i(clk),.rst_edn_ni(rst),.edn_rnd_o(rnd_req),.edn_rnd_i(rnd_rsp),.edn_urnd_o(urnd_req),.edn_urnd_i(urnd_rsp),
 .clk_otp_i(clk),.rst_otp_ni(rst),.otbn_otp_key_o(otp_req),.otbn_otp_key_i(otp_rsp),.keymgr_key_i('0),
 .kmac_app_o(),.kmac_app_i('0),.keymgr_app_i('0),.keymgr_app_o(),.keymgr_sensitive_key_i(prim_mubi_pkg::MuBi4False));
 task automatic bus(input bit wr,input int addr,input int val,output int result,input bit check_data=1);
 @(negedge clk);ti=TL_H2D_DEFAULT;ti.a_valid=1;ti.a_opcode=wr?PutFullData:Get;
 ti.a_size=2;ti.a_mask=15;ti.a_address=addr;ti.a_data=val;
 ti.a_user.cmd_intg=get_cmd_intg(ti);ti.a_user.data_intg=get_data_intg(ti.a_data);
 do @(posedge clk);while(!to.a_ready);
 @(negedge clk);ti.a_valid=0;
 while(!to.d_valid) @(negedge clk);
 if(to.d_error)$fatal(1,"TL error at %h",addr);
 if(to.d_user.rsp_intg!==get_rsp_intg(to) || (!wr && check_data && to.d_user.data_intg!==get_data_intg(to.d_data)))$fatal(1,"TL response integrity addr=%h wr=%b data=%h intg=%h expected=%h",addr,wr,to.d_data,to.d_user.data_intg,get_data_intg(to.d_data));
 result=to.d_data;@(negedge clk);
 endtask
 task automatic wr(input int a,input int v);int q;bus(1,a,v,q);endtask

 task automatic rejected(input int address,input bit write_access=0);
 @(negedge clk);ti=TL_H2D_DEFAULT;ti.a_valid=1;ti.a_opcode=write_access?PutFullData:Get;ti.a_size=2;ti.a_mask=15;ti.a_address=address;ti.a_data=0;
 ti.a_user.cmd_intg=get_cmd_intg(ti);ti.a_user.data_intg=get_data_intg(0);
 do @(posedge clk);while(!to.a_ready);
 @(negedge clk);ti.a_valid=0;while(!to.d_valid)@(negedge clk);
 if(!to.d_error)$fatal(1,"host private/unmapped address unexpectedly accepted %h",address);
 @(negedge clk);$display("PASS denied host address %h",address);
 endtask
 task automatic idle_wait;
 int q;for(int n=0;n<1000000;n++)begin bus(0,'h18,0,q);if(q==0)return;if(q==255)$fatal(1,"OTBN locked");end
 $fatal(1,"idle timeout");endtask
 task automatic execute(input int expected_error);
 int q;int before_entropy;
 before_entropy=entropy_count;wr('h10,'hd8);idle_wait();bus(0,'h1c,0,q);
 if(q!=expected_error)$fatal(1,"ERR_BITS %h expected %h",q,expected_error);
 if(entropy_count<=before_entropy)$fatal(1,"no start reseed");
 $display("PASS execute err=%h EDN words=%0d",q,entropy_count-before_entropy);
 endtask
 task automatic run_vector(input string name,input int err);
 int fd,addr,val,rc,q;int output_addr;logic [255:0] signature_value;string file_name;
 if(!$value$plusargs({name,"=%s"},file_name))$fatal(1,"missing vector %s",name);
 fd=$fopen(file_name,"r");if(!fd)$fatal(1,"input open");
 while(!$feof(fd))begin rc=$fscanf(fd,"%h %h\n",addr,val);if(rc==2)wr(addr,val);end
 $fclose(fd);execute(err);
 if(!$value$plusargs({name,"_expected=%s"},file_name))$fatal(1,"missing expectations");
 fd=$fopen(file_name,"r");
 while(!$feof(fd))begin rc=$fscanf(fd,"%h %h\n",addr,val);if(rc==2)begin
 bus(0,addr,0,q);if(q!==val)$fatal(1,"%s mismatch at %h: %h expected %h",name,addr,q,val);end end
 $fclose(fd);
 if(name=="sign")begin
 if(!$value$plusargs("sig_r_addr=%h",output_addr))$fatal(1,"missing r");
 for(int i=0;i<8;i++)begin bus(0,output_addr+4*i,0,q);signature_value[i*32+:32]=q;end
 $display("SIGNATURE r %h",signature_value);
 if(!$value$plusargs("sig_s_addr=%h",output_addr))$fatal(1,"missing s");
 for(int i=0;i<8;i++)begin bus(0,output_addr+4*i,0,q);signature_value[i*32+:32]=q;end
 $display("SIGNATURE s %h",signature_value);
 end
 $display("PASS official vector %s completion and available output checks",name);
 endtask
 logic [127:0] previous_key;
 int q;
 initial begin
 rnd_rsp='0;urnd_rsp='0;otp_rsp.ack=0;
 repeat(5)@(negedge clk);rst=1;idle_wait();
 if(!dut.init_sec_wipe_done_q || entropy_count<8)$fatal(1,"startup wipe/reseed missing");
 $display("PASS actual full-IP startup internal secure wipe EDN words=%0d",entropy_count);
 // Read-only bring-up primes each foundry-model bank. Uninitialized memory data has no valid ECC.
 // Response control integrity remains checked; no contents are deposited or wipe skipped.
 bus(0,'h8000,0,q,0);bus(0,'h4000,0,q,0);bus(0,'h5000,0,q,0);
 wr('h9ffc,'h12345678);bus(0,'h9ffc,0,q);if(q!='h12345678)$fatal(1,"public last word");
 rejected('ha000);rejected('hbffc);rejected('ha000,1);rejected('hbffc,1);
 run_vector("private_boundary",0);
 bus(0,'h8000,0,q);if(q!=123)$fatal(1,"private lower boundary alias");
 bus(0,'h8004,0,q);if(q!=123)$fatal(1,"private upper boundary alias");
 previous_key=dut.otbn_dmem_scramble_key;wr('h10,'hc3);idle_wait();
 if(dut.otbn_dmem_scramble_key===previous_key)$fatal(1,"DMEM crypto erase key unchanged");
 $display("PASS DMEM crypto erase changes array-wide key, including private scratch; not physical zeroization");
 run_vector("base_mult",0);run_vector("sign",0);run_vector("verify",0);run_vector("invalid_mode",8);
 $display("PASS full OTBN IP functional ECC/scrambling/wipe/reseed, synthetic external EDN; no entropy security claim");
 $finish;end
 initial begin #200000000;$fatal(1,"global timeout");end
endmodule
