#!/usr/bin/env python3
"""Execute the actual RV32 ELF functions; this is not an Ibex timing model."""
import pathlib, sys, json, hashlib, struct, os
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent/'.tools'))
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32
from unicorn.riscv_const import UC_RISCV_REG_SP, UC_RISCV_REG_RA, UC_RISCV_REG_A0
from elftools.elf.elffile import ELFFile
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives import hashes
root=pathlib.Path(__file__).resolve().parent
u=Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
for a,n in [(0,0x40000),(0x10000000,0x4000),(0x20000000,0x10000),(0x40000000,0x1000)]: u.mem_map(a,n)
with pathlib.Path(os.environ.get('TEST_ELF',root/'build/u2f.elf')).open('rb') as f:
 e=ELFFile(f)
 for s in e.iter_sections():
  if s['sh_flags']&2 and s['sh_type']!='SHT_NOBITS':u.mem_write(s['sh_addr'],s.data())
 symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
u.mem_write(0x40000020,struct.pack('<II',1,1)) # deterministic TEST entropy only
results=[]
def call(name,args):
 sp=0x10004000; low=[sp]
 u.reg_write(UC_RISCV_REG_SP,sp);u.reg_write(UC_RISCV_REG_RA,0x30000)
 for i,a in enumerate(args):u.reg_write(UC_RISCV_REG_A0+i,a)
 u.mem_write(sp-4096,b'\xa5'*4096)
 u.emu_start(symbols[name],0x30000,count=30000000)
 water=bytes(u.mem_read(sp-4096,4096)); changed=[i for i,v in enumerate(water) if v!=0xa5]
 low[0]=sp-4096+min(changed) if changed else sp
 from unicorn.riscv_const import UC_RISCV_REG_PC
 assert u.reg_read(UC_RISCV_REG_PC)==0x30000,name+' exceeded instruction limit'
 results.append(dict(function=name,stack_written_highwater=sp-low[0]))
 return u.reg_read(UC_RISCV_REG_A0)
k=0x10002800;p=k+64;digest=p+128;sig=digest+64
u.mem_write(k,(2).to_bytes(32,'big'))
assert call('ecc_compute_public_p256r1',[k,p])==0
pub=bytes(u.mem_read(p,64)); expected=ec.derive_private_key(2,ec.SECP256R1()).public_key()
assert pub==expected.public_numbers().x.to_bytes(32,'big')+expected.public_numbers().y.to_bytes(32,'big')
hashval=hashlib.sha256(b'OpenDonz RV32 checkpoint').digest();u.mem_write(digest,hashval)
assert call('ecdsa_sign_p256r1',[digest,sig,k])==0
s=bytes(u.mem_read(sig,64));expected.verify(utils.encode_dss_signature(int.from_bytes(s[:32],'big'),int.from_bytes(s[32:],'big')),hashval,ec.ECDSA(utils.Prehashed(hashes.SHA256())))
apdu=sig+128;resp=apdu+128;length=resp+1024
u.mem_write(apdu,bytes.fromhex('00030000000000'))
call('u2f_apdu_command_do',[apdu,7,resp,length]);n=struct.unpack('<I',u.mem_read(length,4))[0]
assert bytes(u.mem_read(resp,n))==b'U2F_V2'+bytes.fromhex('9000')
(root/'build'/('rfc-execution.json' if os.environ.get('TEST_ELF') else 'execution.json')).write_text(json.dumps(dict(status='PASS',elf_sha256=hashlib.sha256(pathlib.Path(os.environ.get('TEST_ELF',root/'build/u2f.elf')).read_bytes()).hexdigest(),model='Unicorn RV32; function tests; synthetic entropy; no cycles or USB RTL validation',results=results,limitations='Written-byte watermark is a lower bound on allocated peak stack; no min-SP hook, instruction count or Ibex cycle measurement'),indent=2)+'\n')
print(json.dumps(results,indent=2))
