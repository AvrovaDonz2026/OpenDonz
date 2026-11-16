#!/usr/bin/env python3
"""Independent native/RV32 P256 qualification; synthetic entropy is test-only."""
import ctypes, hashlib, json, pathlib, runpy, subprocess, sys, struct, os
root=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(root/'.tools'))
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives import hashes
v=root/'vendor/mbedtls-e185d7fd85499c8ce5ca2a54f5cf8fe7dbe3f8df'
files=['bignum','bignum_core','bignum_mod','bignum_mod_raw','ecp','ecp_curves','ecdsa','asn1parse','asn1write','platform','platform_util','memory_buffer_alloc','constant_time']
stub=root/'build/native-entropy.c'
stub.write_text('#include <stdint.h>\n#include <stddef.h>\nint mode; void test_entropy(int m){mode=m;}\nint random_gen(void *i,uint8_t *p,size_t n){(void)i;if(mode==1)return -1;unsigned char nonce[32]={0xA6,0xE3,0xC5,0x7D,0xD0,0x1A,0xBE,0x90,0x08,0x65,0x38,0x39,0x83,0x55,0xDD,0x4C,0x3B,0x17,0xAA,0x87,0x33,0x82,0xB0,0xF2,0x4D,0x61,0x29,0x49,0x3D,0x8A,0xAD,0x60};size_t j=0;while(n--){*p++=mode==3?nonce[j++%32]:(mode==2?0:1);}return 0;}\n')
libpath=root/'build/p256-native.dylib'
subprocess.run([os.environ.get('HOST_CC','clang'),'-shared','-fPIC','-Oz','-Wall','-Wextra','-Werror','-DMBEDTLS_CONFIG_FILE="opendonz_crypto_config.h"','-I'+str(root/'port'),'-I'+str(root/'vendor/u2f-token-2c19a75c31096e19cbcfcedeae6bb18077eabac0/src'),'-I'+str(v/'include'),'-I'+str(v/'library'),*[str(v/'library'/(x+'.c')) for x in files],str(root/'port/ecc.c'),str(stub),'-o',str(libpath)],check=True)
lib=ctypes.CDLL(str(libpath));lib.ecc_compute_public_p256r1.argtypes=[ctypes.c_void_p]*2;lib.ecc_compute_public_p256r1.restype=ctypes.c_void_p
lib.ecdsa_sign_p256r1.argtypes=[ctypes.c_void_p]*3;lib.ecdsa_sign_p256r1.restype=ctypes.c_int
f=runpy.run_path(str(root/'test_rv32.py'));u,call=f['u'],f['call'];k,p,d,s=f['k'],f['p'],f['digest'],f['sig']
n=int('ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551',16)
scalars=[('0',0),('1',1),('2',2),('n-2',n-2),('n-1',n-1),('n',n)]+[('sha256-'+str(i),int.from_bytes(hashlib.sha256(('OpenDonz edge '+str(i)).encode()).digest(),'big')%(n-1)+1) for i in range(8)]
# RFC 6979 A.2.5 P-256/SHA-256 public key and ECDSA verification KAT.
x=int('C9AFA9D845BA75166B5C215767B1D6934E50C3DB36E89B127B8A622B120F6721',16)
scalars += [('RFC6979-A.2.5',x)]
rows=[]
for label,scalar in scalars:
 key=scalar.to_bytes(32,'big');valid=0<scalar<n
 expected=None
 if valid:
  pub=ec.derive_private_key(scalar,ec.SECP256R1()).public_key();q=pub.public_numbers();expected=q.x.to_bytes(32,'big')+q.y.to_bytes(32,'big')
 native=ctypes.create_string_buffer(b'\xcc'*64,64);lib.test_entropy(0)
 nr=lib.ecc_compute_public_p256r1(key,native);u.mem_write(k,key);u.mem_write(p,b'\xcc'*64);rr=call('ecc_compute_public_p256r1',[k,p]);ro=bytes(u.mem_read(p,64))
 assert (not nr and rr==0 and native.raw==ro==expected) if valid else (nr and rr==p and native.raw==ro==b'\xcc'*64),label
 h=hashlib.sha256(('OpenDonz sign '+label).encode()).digest();ns=ctypes.create_string_buffer(b'\xcc'*64,64)
 sr=lib.ecdsa_sign_p256r1(h,ns,key);u.mem_write(d,h);u.mem_write(s,b'\xcc'*64);rs=call('ecdsa_sign_p256r1',[d,s,k]);so=bytes(u.mem_read(s,64))
 assert ns.raw==so,label+' native/RV32 signature mismatch'
 if valid:
  assert sr==rs==0
  pub.verify(utils.encode_dss_signature(int.from_bytes(so[:32],'big'),int.from_bytes(so[32:],'big')),h,ec.ECDSA(utils.Prehashed(hashes.SHA256())))
 else: assert sr==-1 and rs==0xffffffff and so==b'\xcc'*64
 rows.append(dict(label=label,scalar=key.hex(),public_key=ro.hex(),signature=so.hex(),valid=valid,passed=True))
# Check the published RFC public point and signature independently (randomized
# signing API does not claim RFC6979 deterministic nonce generation).
rfc=rows[-1];assert rfc['public_key']==('60fed4ba255a9d31c961eb74c6356d68c049b8923b61fa6ce669622e60f29fb6'+'7903fe1008b8bc99a41ae9e95628bc64f2f1b20c2d7e9f5177a3c294d4462299')
r=int('EFD48B2AACB6A8FD1140DD9CD45E81D69D2C877B56AAF991C34D0EA84EAF3716',16);ss=int('F7CB1C942D657C41D436C7A1B6E29F65F3E900DBB9AFF4064DC4AB2F843ACDA8',16)
ec.derive_private_key(x,ec.SECP256R1()).public_key().verify(utils.encode_dss_signature(r,ss),b'sample',ec.ECDSA(hashes.SHA256()))
# Test-only link wrapping injects the published nonce without changing firmware.
wrapped=root/'build/rfc-entropy.c';wrapped.write_text(stub.read_text().replace('random_gen(', '__wrap_random_gen('))
cc=os.environ.get('HOST_CC','clang');obj=root/'build/rfc-entropy.o'
subprocess.run([cc,'--target=riscv32-unknown-elf','-march=rv32imc','-mabi=ilp32','-Oz','-ffreestanding','-c',str(wrapped),'-o',str(obj)],check=True)
objects=[root/'build'/(name+'.o') for name in ['u2f-apdu','u2f-hid','sha256','hmac',*['mbed-'+name for name in files],'ecc','platform','crt0']]
testelf=root/'build/rfc-test.elf'
subprocess.run([os.environ.get('LD','ld.lld'),'-m','elf32lriscv','-T',str(root/'port/link.ld'),'--gc-sections','--undefined=u2f_apdu_command_do','--wrap=random_gen',*[str(o) for o in objects],str(obj),'-o',str(testelf)],check=True)
os.environ['TEST_ELF']=str(testelf)
rf=runpy.run_path(str(root/'test_rv32.py'));os.environ.pop('TEST_ELF')
ru,rc=rf['u'],rf['call'];ru.mem_write(rf['symbols']['mode'],struct.pack('<I',3));lib.test_entropy(3)
key=x.to_bytes(32,'big');hv=hashlib.sha256(b'sample').digest();out=ctypes.create_string_buffer(64)
assert lib.ecdsa_sign_p256r1(hv,out,key)==0
ru.mem_write(k,key);ru.mem_write(d,hv);assert rc('ecdsa_sign_p256r1',[d,s,k])==0
assert out.raw==bytes(ru.mem_read(s,64))==r.to_bytes(32,'big')+ss.to_bytes(32,'big')
errors=[]
for mode,label in [(1,'entropy-unavailable'),(2,'zero-entropy-rejection-limit')]:
 lib.test_entropy(mode);u.mem_write(0x40000020,struct.pack('<II',0 if mode==1 else 1,0));u.mem_write(k,(2).to_bytes(32,'big'))
 for sign in [False,True]:
  out=ctypes.create_string_buffer(b'\xcc'*64,64);u.mem_write(p,b'\xcc'*64)
  nr=lib.ecdsa_sign_p256r1(h,out,(2).to_bytes(32,'big')) if sign else lib.ecc_compute_public_p256r1((2).to_bytes(32,'big'),out)
  rr=call('ecdsa_sign_p256r1',[d,p,k]) if sign else call('ecc_compute_public_p256r1',[k,p])
  assert (nr==-1 and rr==0xffffffff) if sign else (nr and rr==p)
  assert out.raw==bytes(u.mem_read(p,64))==b'\xcc'*64
  errors.append(dict(case=label,operation='sign' if sign else 'public',passed=True))
u.mem_write(0x40000020,struct.pack('<II',1,1));lib.test_entropy(0)
report=dict(status='PASS',qualified=True,implementation='Mbed TLS 3.6.5',commit='e185d7fd85499c8ce5ca2a54f5cf8fe7dbe3f8df',elf_sha256=hashlib.sha256((root/'build/u2f.elf').read_bytes()).hexdigest(),results=rows,error_cases=errors,known_vector='RFC6979 A.2.5: published public point and exact r/s using test-only published nonce injection on native and RV32; randomized production signatures independently verified',limitations='Not CAVP certification or side-channel signoff; synthetic entropy only; raw adapter has no public-key input')
(root/'build/crypto-edge.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: 14 boundary cases + RFC public KAT; signatures native/RV32 identical and independently verified; four entropy failures')
