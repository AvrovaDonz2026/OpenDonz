// Deterministic digital FS host. Independent reflected USB CRC and NRZI codec.
#include "Vsoc_usb_top.h"
#include "verilated.h"
#include <vector>
#include <iostream>
#include <stdexcept>
#include <string>
#include <algorithm>
using Bytes=std::vector<unsigned char>;
Vsoc_usb_top d;
std::vector<int> wave;



void require(bool ok,const std::string& s){if(!ok)throw std::runtime_error(s);}
void step(){
 d.clk_i=0; d.eval();
 int tx=(d.usb_dp_o<<1)|d.usb_dn_o;
 wave.push_back(d.usb_oe_o?tx:-1);
 d.clk_i=1;d.eval();
}
void cycles(int n){while(n--)step();}
void line(int state,int n=4){d.usb_dp_i=(state>>1)&1;d.usb_dn_i=state&1;d.usb_d_i=d.usb_dp_i;cycles(n);}
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
void clear(){wave.clear();}

void setup(Bytes b,int addr){clear();token(13,0,addr);cycles(8);data(3,b);cycles(180);require(response()==Bytes({0x80,(unsigned char)pid(2)}),"SETUP ACK");}
Bytes get(int ep,int addr,bool ack=true){clear();token(9,ep,addr);for(int i=0;i<6000;i++){step();if(wave.size()>2&&wave[wave.size()-2]>=0&&wave.back()<0)break;}auto b=response();if(ack && b.size()>2){line(2,8);send({0x80,(unsigned char)pid(2)});cycles(60);}else cycles(200);return b;}
Bytes body(Bytes b){require(b.size()>=4,"data response length");Bytes p(b.begin()+2,b.end()-2);auto c=crc16(p);require(b[b.size()-2]==(c&255)&&b.back()==(c>>8),"independent IN CRC");return p;}
void statusOut(int addr){clear();token(1,0,addr);cycles(8);data(11,{});cycles(180);require(response()==Bytes({0x80,(unsigned char)pid(2)}),"status OUT ACK");}
void out(Bytes b,int addr,int dp=3){clear();token(1,1,addr);cycles(8);data(dp,b);cycles(180);require(response()==Bytes({0x80,(unsigned char)pid(2)}),"HID OUT ACK");}
Bytes poll(int addr){for(int i=0;i<100;i++){auto b=get(1,addr,true);if(b.size()>2){return body(b);}cycles(500);}throw std::runtime_error("HID response timeout");}
int main(int argc,char**argv){Verilated::commandArgs(argc,argv);try{
 d.rng_valid_i=1;d.rng_data_i=0x42; // Test-only deterministic entropy.
 d.rst_ni=0;d.link_reset_i=0;line(2,30);d.rst_ni=1;cycles(30000);
 setup({0x80,6,0,1,0,0,18,0},0);auto descriptor=body(get(0,0));require(descriptor.size()==18&&descriptor[0]==18&&descriptor[1]==1&&descriptor[7]==64,"device descriptor");statusOut(0);
 setup({0,5,5,0,0,0,0,0},0);auto retry=get(0,0,false);require(body(retry).empty(),"SET_ADDRESS status ZLP");require(get(0,0)==retry,"unacked status retry uses old address");
 clear();token(9,0,0);cycles(300);require(response().empty(),"old address silent after ACK");
 setup({0x80,6,0,2,0,0,255,0},5);auto config=body(get(0,5));require(config.size()==41&&config[2]==41&&config[4]==1,"configuration descriptor");statusOut(5);
 setup({0,9,1,0,0,0,0,0},5);require(body(get(0,5)).empty(),"configuration status");
 setup({0x81,6,0,0x22,0,0,255,0},5);auto report=body(get(0,5));require(report.size()==34&&report[0]==6,"HID report descriptor");statusOut(5);
 Bytes init(64,0);for(int i=0;i<4;i++)init[i]=255;init[4]=0x86;init[6]=8;for(int i=0;i<8;i++)init[i+7]=i+1;clear();token(1,1,5);cycles(8);data(3,init,true);cycles(180);require(response().empty(),"bad CRC OUT rejected");require(get(1,5)==Bytes({0x80,(unsigned char)pid(10)}),"bad CRC must not reach firmware");
 out(init,5);auto resp=poll(5);require(resp.size()==64&&resp[4]==0x86&&resp[6]==17,"firmware HID INIT response");for(int i=0;i<8;i++)require(resp[i+7]==i+1,"INIT nonce");
 out(init,5);require(get(1,5)==Bytes({0x80,(unsigned char)pid(10)}),"duplicate OUT must not produce second INIT");
 Bytes version(64,0);std::copy(resp.begin()+15,resp.begin()+19,version.begin());version[4]=0x83;version[6]=7;version[8]=3;out(version,5,11);resp=poll(5);require(resp[4]==0x83&&resp[6]==8&&Bytes(resp.begin()+7,resp.begin()+15)==Bytes({'U','2','F','_','V','2',0x90,0}),"firmware VERSION response");
 setup({0x80,0xff,0,0,0,0,0,0},5);auto stalled=get(0,5,false);require(stalled==Bytes({0x80,(unsigned char)pid(14)}),"unsupported request STALL");
 setup({0x80,6,0,1,0,0,8,0},5);require(body(get(0,5))==Bytes(descriptor.begin(),descriptor.begin()+8),"new SETUP clears stall and truncates descriptor");statusOut(5);
 d.link_reset_i=1;cycles(8);d.link_reset_i=0;cycles(100);
 clear();token(9,0,5);cycles(200);require(response().empty(),"link reset clears address");
 setup({0x80,6,0,1,0,0,18,0},0);auto first=get(0,0,false);require(body(first)==descriptor,"descriptor after link reset");require(get(0,0)==first,"descriptor timeout retry identical");statusOut(0);
 std::cout<<"PASS digital USB D+/D- -> EP0 descriptor/address/configuration -> actual Ibex HID INIT/U2F_VERSION\n";return 0;
 }catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<"\n";return 1;}}
