import json,pathlib,re
from elftools.elf.elffile import ELFFile
from cryptography.hazmat.primitives.asymmetric import ec,utils
from cryptography.hazmat.primitives import hashes
R=pathlib.Path(__file__).resolve().parent; B=R/'build/vectors'
n=int('ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551',16)
def initial(name):
 with (B/(name+'.elf')).open('rb') as f:
  e=ELFFile(f); syms=e.get_section_by_name('.symtab'); data=e.get_section_by_name('.data'); raw=data.data(); base=data['sh_addr']
  return {s.name:raw[s['st_value']-base:] for s in syms.iter_symbols() if s['st_shndx']==e.get_section_index('.data')}
def regs(name): return {k:int(v,16) for k,v in re.findall(r'(\w+)\s*=\s*0x([0-9a-fA-F]+)',(B/(name+'-regs.txt')).read_text())}
name='p256_ecdsa_sign_test'; d=initial(name); g=regs(name)
priv=(int.from_bytes(d['d0'][:64],'little')+int.from_bytes(d['d1'][:64],'little'))%n
key=ec.derive_private_key(priv,ec.SECP256R1());sig=utils.encode_dss_signature(g['w0'],g['w1']);digest=int.from_bytes(d['msg'][:32],'little').to_bytes(32,'big')
key.public_key().verify(sig,digest,ec.ECDSA(utils.Prehashed(hashes.SHA256())))
rejected=False
try: key.public_key().verify(sig,bytes([digest[0]^1])+digest[1:],ec.ECDSA(utils.Prehashed(hashes.SHA256())))
except Exception: rejected=True
assert rejected
name='p256_base_mult_test'; d=initial(name); g=regs(name)
priv=(int.from_bytes(d['d0'][:64],'little')+int.from_bytes(d['d1'][:64],'little'))%n
point=ec.derive_private_key(priv,ec.SECP256R1()).public_key().public_numbers()
# Upstream test exposes affine coordinates in w0/w1.
assert (g['w0'],g['w1'])==(point.x,point.y)
result=dict(independent_backend='Python cryptography/OpenSSL SECP256R1',public_key='PASS',signature='PASS',changed_digest_rejected=rejected)
(B/'independent.json').write_text(json.dumps(result,indent=2)+'\n'); print(result)
