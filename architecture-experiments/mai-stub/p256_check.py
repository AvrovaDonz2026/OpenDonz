#!/usr/bin/env python3
"""Execute the complete official entrypoint with an isolated memory view."""
import os,pathlib,subprocess,sys,json
R=pathlib.Path('/Users/zxy/OpenDonz/crypto-hw');OT=pathlib.Path('/Users/zxy/opentitan');HALF='--half-dmem' in sys.argv;B=pathlib.Path(__file__).resolve().parent/'p256';B.mkdir(parents=True,exist_ok=True)
O=R/'build'/('imem8-dmem16' if HALF else 'imem8')/'otbn';C=OT/'sw/otbn/crypto';U=O/'util'
paths=[OT,OT/'util',U,O/'dv/otbnsim']
os.environ['PYTHONPATH']=':'.join(map(str,paths));os.environ['RV32_TOOL_AS']='/opt/homebrew/bin/riscv64-elf-as';os.environ['RV32_TOOL_LD']='/opt/homebrew/bin/riscv64-elf-ld'
sys.path[:0]=list(map(str,paths))
from elftools.elf.elffile import ELFFile
from sim.load_elf import load_elf
from sim.standalonesim import StandaloneSim
from shared.mem_layout import get_memory_layout
from cryptography.hazmat.primitives.asymmetric import ec,utils
from cryptography.hazmat.primitives import hashes
N=int('ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551',16)
def main():
 assert get_memory_layout().imem_size_bytes==8192
 assert get_memory_layout().dmem_size_bytes==(16384 if HALF else 32768)
 assert get_memory_layout().dmem_bus_size_bytes==(8192 if HALF else 16384)
 sources=['run_p256','p256_base','p256_b2a','p256_isoncurve','p256_isoncurve_check','p256_isoncurve_proj','p256_a2b','p256_shared_key','p256_sign','p256_verify']
 for name in sources:
  subprocess.run([sys.executable,str(U/'otbn_as.py'),'-march=rv32i_zicsr','-o',str(B/(name+'.o')),str(C/(name+'.s'))],check=True)
 elf=B/'run_p256.elf';subprocess.run([sys.executable,str(U/'otbn_ld.py'),'-m','elf32lriscv','-o',str(elf)]+[str(B/(n+'.o')) for n in sources],check=True)
 with elf.open('rb') as f:
  e=ELFFile(f);sections={s.name:dict(address=s['sh_addr'],size=s['sh_size']) for s in e.iter_sections() if s.name in ('.text','.data','.bss','.scratchpad')}
 from sim.decode import _decode_word,IllegalInsn
 import struct,collections,hashlib
 with elf.open('rb') as f:
  text=ELFFile(f).get_section_by_name('.text').data()
 counts=collections.Counter();special=[]
 for pc,(word,) in enumerate(struct.iter_unpack('<I',text)):
  insn=_decode_word(pc*4,word)
  assert not isinstance(insn,IllegalInsn),(pc*4,word)
  counts[insn.insn.mnemonic]+=1
  for attr,lo,hi in [('csr',0x7e0,0x7e0),('wsr',10,15)]:
   val=getattr(insn,attr,None)
   if val is not None:
    special.append(dict(pc=pc*4,instruction=insn.insn.mnemonic,kind=attr,address=val))
    assert not (lo<=val<=hi or (attr=='csr' and val==0xfca)),(pc*4,attr,val)
 (B/'instruction-audit.json').write_text(json.dumps(dict(elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),text_bytes=len(text),instruction_count=len(text)//4,mnemonics=counts,special_register_accesses=special,mai_accesses=0,method='Decode every linked .text word with official OTBN decoder; reject MAI CSR/WSR addresses'),indent=2)+'\n')
 def execute(name,mode,values,expected_error=0):
  sim=StandaloneSim();load_elf(sim,str(elf));sim.state.wsrs.set_sideload_keys(int('deadbeef'*16,16),int('baadf00d'*16,16))
  v={'mode':mode.to_bytes(4,'little')};v.update(values);(B/(name+'-inputs.json')).write_text(json.dumps({k:x.hex() for k,x in v.items()},indent=2)+'\n');sim.load_dmem_vars(v);sim.state.ext_regs.commit();sim.start(True);cycles=sim.run(False,None)
  err=sim.state.ext_regs.read('ERR_BITS',False);assert err==expected_error,(name,err)
  raw=sim.dump_data();(B/(name+'.bin')).write_bytes(raw)
  # dump_data uses a validity byte followed by each little-endian 32-bit word.
  assert len(raw)==(16384 if HALF else 32768)//4*5
  data=b''.join(raw[i+1:i+5] for i in range(0,len(raw),5))
  def get(label,n=32):return int.from_bytes(data[sim.symbols[label]:sim.symbols[label]+n],'little')
  result=dict(test=name,cycles=cycles,err_bits=err,source='ISA model; synthetic entropy; initial wipe bypassed by upstream standalone harness')
  (B/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
  return get,result
 rows=[]
 def record(row):
  rows.append(row);(B/'results.json').write_text(json.dumps(dict(sections=sections,imem_bytes=8192,complete=False,results=rows),indent=2)+'\n')
 key=ec.derive_private_key(7,ec.SECP256R1());point=key.public_key().public_numbers();shares={'d0_io':(7).to_bytes(64,'little'),'d1_io':bytes(64)}
 get,row=execute('base_mult',0x3c6,shares);assert (get('x'),get('y'))==(point.x,point.y);record(row)
 digest=bytes(range(32));msg=int.from_bytes(digest,'big').to_bytes(32,'little')
 get,row=execute('sign',0x734,dict(shares,msg=msg));r,s=get('r'),get('s');key.public_key().verify(utils.encode_dss_signature(r,s),digest,ec.ECDSA(utils.Prehashed(hashes.SHA256())));record(row)
 values=dict(msg=msg,r=r.to_bytes(32,'little'),s=s.to_bytes(32,'little'),x=point.x.to_bytes(32,'little'),y=point.y.to_bytes(32,'little'))
 get,row=execute('verify',0x5d8,values);assert get('ok',4)==0x739 and get('x_r')==r;record(row)
 values['msg']=bytes(32);get,row=execute('verify_changed_digest',0x5d8,values);assert get('x_r')!=r;record(row)
 get,row=execute('invalid_mode',0,{'d0_io':bytes(64),'d1_io':bytes(64),'k0_io':bytes(64),'k1_io':bytes(64)},8);record(row)
 get,row=execute('keygen',0x497,{});priv=(get('d0_io',64)+get('d1_io',64))%N;pub=ec.derive_private_key(priv,ec.SECP256R1()).public_key().public_numbers();assert (get('x'),get('y'))==(pub.x,pub.y);record(row)
 for name,mode in [('sideload_keygen',0x7e),('sideload_sign',0x64d),('sideload_ecdh',0x2f1),('ecdh',0x1ad),('point_on_curve',0x6aa),('arith_share',0x31b),('sign_config_k',0x563)]:
  vals=dict(shares,attestation_additional_seed=bytes(64),msg=msg,x=point.x.to_bytes(32,'little'),y=point.y.to_bytes(32,'little'),k0_io=(11).to_bytes(64,'little'),k1_io=bytes(64))
  get,row=execute(name,mode,vals)
  if name=='sideload_keygen': sideload_point=(get('x'),get('y'))
  if name=='sideload_sign': ec.EllipticCurvePublicNumbers(*sideload_point,ec.SECP256R1()).public_key().verify(utils.encode_dss_signature(get('r'),get('s')),digest,ec.ECDSA(utils.Prehashed(hashes.SHA256())))
  if name=='sign_config_k':key.public_key().verify(utils.encode_dss_signature(get('r'),get('s')),digest,ec.ECDSA(utils.Prehashed(hashes.SHA256())))
  if name=='ecdh':
   expected=ec.derive_private_key(49,ec.SECP256R1()).public_key().public_numbers();assert get('ecdh_x0')^get('ecdh_x1')==expected.x;assert get('ecdh_y0')^get('ecdh_y1')==expected.y
  if name=='point_on_curve':assert get('ok',4)==0x739
  if name=='arith_share':assert (get('d0_io',64)+get('d1_io',64))%N==7
  record(row)
 (B/'results.json').write_text(json.dumps(dict(sections=sections,imem_bytes=8192,complete=True,results=rows),indent=2)+'\n');print(json.dumps(rows),flush=True)
if __name__=='__main__':main()
