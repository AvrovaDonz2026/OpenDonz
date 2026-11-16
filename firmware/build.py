#!/usr/bin/env python3
import pathlib, subprocess, json, hashlib, os
root=pathlib.Path(__file__).resolve().parent
up=root/'vendor/u2f-token-2c19a75c31096e19cbcfcedeae6bb18077eabac0/src'
ecc=root/'vendor/mbedtls-e185d7fd85499c8ce5ca2a54f5cf8fe7dbe3f8df'
b=root/'build'; b.mkdir(exist_ok=True)
cc=os.environ.get('CC','clang')
flags=['--target=riscv32-unknown-elf','-march=rv32imc','-mabi=ilp32','-Oz','-g','-ffreestanding','-fno-builtin','-fstack-usage','-ffunction-sections','-fdata-sections','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-DMBEDTLS_CONFIG_FILE="opendonz_crypto_config.h"','-I'+str(root/'port/include'),'-I'+str(root/'port'),'-I'+str(up),'-I'+str(ecc/'include'),'-I'+str(ecc/'library')]
sources=[up/x for x in ['u2f-apdu.c','u2f-hid.c','sha256.c','hmac.c']]+[ecc/'library'/x for x in ['bignum.c','bignum_core.c','bignum_mod.c','bignum_mod_raw.c','ecp.c','ecp_curves.c','ecdsa.c','asn1parse.c','asn1write.c','platform.c','platform_util.c','memory_buffer_alloc.c','constant_time.c']]+[root/'port'/x for x in ['ecc.c','platform.c','crt0.S']]
objects=[]
for s in sources:
 o=b/(('mbed-' if ecc in s.parents else '')+s.stem+'.o'); subprocess.run([cc,*flags,'-c',str(s),'-o',str(o)],check=True); objects.append(str(o))
subprocess.run([os.environ.get('LD','ld.lld'),'-m','elf32lriscv','-T',str(root/'port/link.ld'),'-Map='+str(b/'u2f.map'),'--gc-sections','--undefined=u2f_apdu_command_do',*objects,'-o',str(b/'u2f.elf')],check=True)
for tool,args,name in [('llvm-size',['-A'],'size.txt'),('llvm-readelf',['-h','-A','-S'],'elf.txt')]:
 with (b/name).open('w') as f: subprocess.run([os.environ.get(tool.upper().replace('-','_'),tool),*args,str(b/'u2f.elf')],stdout=f,check=True)
inputs=set(sources) | set((root/'port').rglob('*')) | set(up.glob('*.h')) | set(ecc.rglob('*.h')) | set(ecc.rglob('*.inc'))
manifest={str(s.relative_to(root)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sorted(inputs) if s.is_file()}
manifest['compiler']=subprocess.check_output([cc,'--version'],text=True)
(b/'inputs.json').write_text(json.dumps(manifest,indent=2)+'\n')
p=b/'size.txt'; p.write_text(p.read_text().rstrip()+'\n')
print(p.read_text())

frames=[]
for su in [pathlib.Path(o).with_suffix('.su') for o in objects if pathlib.Path(o).with_suffix('.su').exists()]:
 for line in su.read_text().splitlines():
  location,size,kind=line.split('\t'); frames.append(dict(function=location.rsplit(':',1)[-1],bytes=int(size),kind=kind,source=location))
(b/'stack.json').write_text(json.dumps(dict(note='Per-function static frames, NOT call-chain bounds; indirect calls and interrupts need analysis',frames=sorted(frames,key=lambda f:-f['bytes'])),indent=2)+'\n')
