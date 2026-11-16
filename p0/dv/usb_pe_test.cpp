// Deterministic digital FS host. Independent reflected USB CRC and NRZI codec.
#include "Vusb_fs_nb_pe_top.h"
#include "verilated.h"
#include <vector>
#include <iostream>
#include <stdexcept>
#include <string>
#include <algorithm>
using Bytes=std::vector<unsigned char>;
Vusb_fs_nb_pe_top d;
std::vector<int> wave;
Bytes received, payload;
int sof=0, validsof=0;
int acked=0, rollback=0, ended=0, inrollback=0, crc5err=0, crc16err=0, piderr=0, stufferr=0;
void require(bool ok,const std::string& s){if(!ok)throw std::runtime_error(s);}
void step(){
 d.clk_i=0; d.in_ep_data_i=d.in_ep_get_addr_o<payload.size()?payload[d.in_ep_get_addr_o]:0;
 d.in_ep_data_done_i=d.in_ep_get_addr_o>=payload.size()?3:0; d.eval();
 if(d.out_ep_data_put_o){if(!d.out_ep_full_i)require(d.out_ep_put_addr_o==std::min<size_t>(received.size(),63),"OUT byte address");received.push_back(d.out_ep_data_o);}
 sof+=d.sof_detected_o;validsof+=d.sof_valid_o;
 acked+=d.out_ep_acked_o; rollback+=d.out_ep_rollback_o; ended+=d.in_ep_xact_end_o;
 inrollback+=d.in_ep_rollback_o; crc5err+=d.rx_crc5_err_o; crc16err+=d.rx_crc16_err_o;
 piderr+=d.rx_pid_err_o; stufferr+=d.rx_bitstuff_err_o;
 int tx=(d.usb_dp_o<<1)|d.usb_dn_o; if(d.cfg_pinflip_i)tx=((tx&1)<<1)|(tx>>1);
 wave.push_back(d.usb_oe_o?tx:-1);
 d.clk_i=1;d.eval();
}
void cycles(int n){while(n--)step();}
void line(int state,int n=4){if(d.cfg_pinflip_i)state=((state&1)<<1)|(state>>1);d.usb_dp_i=(state>>1)&1;d.usb_dn_i=state&1;d.usb_d_i=d.usb_dp_i;cycles(n);}
unsigned crc(unsigned value,int n,unsigned init,unsigned poly,unsigned mask){unsigned c=init;for(int i=0;i<n;i++){bool mix=(c^(value>>i))&1;c>>=1;if(mix)c^=poly;}return (~c)&mask;}
unsigned crc16(const Bytes& b){unsigned c=0xffff;for(auto v:b)for(int i=0;i<8;i++){bool mix=(c^(v>>i))&1;c>>=1;if(mix)c^=0xa001;}return c^0xffff;}
Bytes withCRC(Bytes b){unsigned c=crc16(b);b.push_back(c&255);b.push_back(c>>8);return b;}
unsigned pid(unsigned p){return p|((p^15)<<4);}
void send(const Bytes& b,bool badstuff=false){
 int state=2,ones=0;bool injected=false;
 auto bit=[&](int x){if(!x)state=3-state;line(state);};
 for(auto v:b)for(int i=0;i<8;i++){int x=(v>>i)&1;bit(x);ones=x?ones+1:0;if(ones==6){if(badstuff&&!injected){bit(1);injected=true;}else bit(0);ones=0;}}
 line(0,8);line(2,4);
}
void token(int p,int ep=1,int addr=5,bool bad=false){unsigned v=addr|(ep<<7);unsigned c=crc(v,11,31,0x14,31)^(bad?1:0);send({0x80,(unsigned char)pid(p),(unsigned char)v,(unsigned char)((v>>8)|(c<<3))});}
void data(int p,const Bytes& b,bool bad=false,bool badstuff=false){unsigned c=crc16(b)^(bad?1:0);Bytes wire={0x80,(unsigned char)pid(p)};wire.insert(wire.end(),b.begin(),b.end());wire.push_back(c&255);wire.push_back(c>>8);send(wire,badstuff);}
Bytes response(){
 size_t a=0;while(a<wave.size()&&wave[a]<0)a++;if(a==wave.size())return {};
 // Output enable precedes SOP; locate first K and sample bit centers.
 while(a<wave.size()&&wave[a]!=1)a++;
 std::vector<int> bits;int prev=2,ones=0;
 for(size_t i=a+2;i<wave.size()&&wave[i]>0;i+=4){int st=wave[i];int x=st==prev;prev=st;if(ones==6){require(x==0,"TX bit-stuff violation");ones=0;continue;}bits.push_back(x);ones=x?ones+1:0;}
 Bytes b;for(size_t i=0;i+7<bits.size();i+=8){unsigned v=0;for(int j=0;j<8;j++)v|=bits[i+j]<<j;b.push_back(v);}return b;
}
void clear(){sof=validsof=0;wave.clear();received.clear();acked=rollback=ended=inrollback=crc5err=crc16err=piderr=stufferr=0;}
void reset(){
 d.rst_ni=0;line(2,20);
 // Release without a clock edge: protocol state must stay reset until the
 // rising-edge synchronizer has seen two edges. Assertion remains immediate.
 d.in_datatog_we_i=1;d.in_datatog_mask_i=3;d.in_datatog_status_i=3;
 d.rst_ni=1;d.eval();require(!d.in_data_toggle_o&&!d.usb_oe_o,"reset release without clock");
 step();require(!d.in_data_toggle_o,"first release cycle must remain reset");
 step();require(!d.in_data_toggle_o,"second release edge leaves protocol state reset");
 step();require(d.in_data_toggle_o==3,"third edge accepts protocol writes");
 d.in_datatog_we_i=0;d.link_reset_i=1;cycles(2);d.link_reset_i=0;cycles(40);clear();
}
void expectHandshake(int p){cycles(150);auto b=response();require(b==Bytes({0x80,(unsigned char)pid(p)}),"handshake mismatch expected PID "+std::to_string(p)+" got bytes "+std::to_string(b.size()));}
void test(const char* n){std::cout<<"PASS "<<n<<"\n";}
int main(int argc,char**argv){Verilated::commandArgs(argc,argv);try{
 d.cfg_use_diff_rcvr_i=argc>1?std::stoi(argv[1]):0;d.cfg_pinflip_i=argc>2?std::stoi(argv[2]):0;
 std::cout<<"CONFIG diff="<<int(d.cfg_use_diff_rcvr_i)<<" pinflip="<<int(d.cfg_pinflip_i)<<" phase="<<(argc>3?argv[3]:"0")<<"\n";
 d.link_active_i=1;d.dev_addr_i=5;d.diff_rx_ok_i=1;d.out_ep_enabled_i=3;d.in_ep_enabled_i=3;d.out_ep_control_i=1;
 reset();require(!d.usb_oe_o&&!d.in_data_toggle_o&&!d.out_data_toggle_o,"reset state");test("async reset and idle");cycles(argc>3?std::stoi(argv[3]):0);
 token(9);expectHandshake(10);test("IN empty NAK");
 clear();token(9,1,6);cycles(180);require(response().empty(),"wrong address responded");test("address filter");
 clear();token(9,3);cycles(180);require(response().empty(),"invalid endpoint responded");test("endpoint filter");
 clear();d.in_ep_stall_i=2;token(9);expectHandshake(14);d.in_ep_stall_i=0;test("IN STALL");
 clear();token(5,0,0);cycles(60);require(sof&&validsof&&d.frame_index_o==0,"valid SOF");test("SOF valid CRC5 frame index");
 clear();token(5,0,0,true);cycles(60);require(sof&&!validsof&&crc5err,"invalid SOF");test("SOF CRC5 invalidates frame");
 Bytes p={0,0xff,0xff,0xf8,0x55,0xaa,0x01,0x80};
 clear();token(1);cycles(8);data(3,p);expectHandshake(2);require(received==withCRC(p)&&acked==1&&d.out_data_toggle_o==2,"OUT payload/commit/toggle received="+std::to_string(received.size())+" acked="+std::to_string(acked)+" toggle="+std::to_string(d.out_data_toggle_o));test("OUT DATA0 payload CRC16 stuffing ACK toggle");
 clear();token(1);cycles(8);data(3,p);expectHandshake(2);require(rollback&&acked==0&&d.out_data_toggle_o==2,"duplicate rollback");test("duplicate OUT ACK with rollback");
 clear();token(1);cycles(8);data(11,p,true);cycles(180);require(crc16err&&rollback&&response().empty()&&d.out_data_toggle_o==2,"bad CRC16");test("bad CRC16 rejected silently");
 clear();token(1,1,5,true);cycles(8);data(11,p);cycles(180);require(crc5err&&response().empty()&&!acked,"bad CRC5");test("bad token CRC5 rejected");
 clear();d.out_ep_full_i=2;token(1);cycles(8);data(11,p);expectHandshake(10);require(rollback&&!acked,"full rollback");d.out_ep_full_i=0;test("OUT full NAK rollback");
 clear();d.out_ep_stall_i=2;token(1);cycles(8);data(11,p);expectHandshake(14);require(rollback&&!acked,"stall rollback");d.out_ep_stall_i=0;test("OUT STALL rollback");
 clear();token(1);cycles(8);data(11,p,false,true);cycles(180);require(stufferr&&rollback&&response().empty(),"bad bitstuff");test("bit stuffing error rejected");
 clear();send({0x80,0x19});cycles(180);require(piderr&&response().empty(),"bad PID");test("PID complement error");
 clear();token(13,0);cycles(8);data(3,Bytes{0x80,6,0,1,0,0,18,0});expectHandshake(2);require(acked&&d.out_ep_setup_o==1&&(d.in_data_toggle_o&1),"SETUP");test("EP0 SETUP DATA0 ACK and DATA1 initialization");
 // IN data with host ACK: inspect actual serialized bytes and independently computed CRC.
 payload=p;d.in_ep_has_data_i=2;clear();token(9);cycles(10);
 for(int i=0;i<3000;i++){step();if(wave.size()>2&&wave[wave.size()-2]>=0&&wave.back()<0)break;}
 auto b=response();Bytes expected={0x80,(unsigned char)pid(3)};expected.insert(expected.end(),p.begin(),p.end());unsigned c=crc16(p);expected.push_back(c&255);expected.push_back(c>>8);require(b==expected,"IN serialized payload/CRC mismatch");
 line(2,8);send({0x80,(unsigned char)pid(2)});cycles(40);require(ended==1&&(d.in_data_toggle_o&2),"IN ACK commit");test("IN DATA0 bytes stuffing CRC16 host ACK toggle");
 clear();token(9);cycles(3000);require(inrollback&& !ended&&(d.in_data_toggle_o&2),"IN timeout retry state");b=response();require(b.size()>1&&b[1]==pid(11),"IN DATA1 retry");test("IN DATA1 missing ACK timeout rollback");
 clear();d.link_reset_i=1;cycles(4);d.link_reset_i=0;cycles(40);require(!d.in_data_toggle_o&&!d.out_data_toggle_o&&!d.usb_oe_o,"link reset");test("link reset clears toggles and transaction state");
 // Exercise full 64-byte boundary and zero-length OUT.
 payload.clear();d.in_ep_has_data_i=0;Bytes large(64);for(int i=0;i<64;i++)large[i]=(i*73)^0xff;
 clear();token(1);cycles(8);data(3,large);expectHandshake(2);require(received==withCRC(large)&&acked,"64 byte boundary");test("64-byte OUT address boundary");
 clear();token(1);cycles(8);data(11,{});expectHandshake(2);require(received==withCRC({})&&acked,"ZLP");test("zero-length OUT");
 // Full-size and zero-length IN, independently decode all bytes and CRC.
 for(int len: {0,64}){
  payload=Bytes(large.begin(),large.begin()+len);d.in_ep_has_data_i=2;clear();token(9);
  cycles(4000);auto wire=response();Bytes wanted={0x80,(unsigned char)pid(3)};
  auto body=withCRC(payload);wanted.insert(wanted.end(),body.begin(),body.end());
  require(wire==wanted&&inrollback&&!ended,"IN boundary serialized payload and timeout");
  test(len?"64-byte IN and CRC":"zero-length IN and CRC");
 }
 std::cout<<"RESULT PASS: digital USB PE directed regression\n";return 0;
 }catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<"\n";return 1;}}
