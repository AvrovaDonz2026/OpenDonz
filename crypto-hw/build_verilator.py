#!/usr/bin/env python3
"""Build pinned supported simulator locally; never install into global paths."""
import hashlib,json,pathlib,subprocess,tarfile,os
R=pathlib.Path(__file__).resolve().parent
B=R/'build/tools';B.mkdir(parents=True,exist_ok=True)
archive=B/'verilator-v5.048.tar.gz'
if not archive.exists():
 with archive.open('wb') as f:subprocess.run(['gh','api','repos/verilator/verilator/tarball/v5.048'],stdout=f,check=True)
expected='006c847e8cb95de40d04d29b459c1ab26bf65c5a4d719ef9f2061b1cc494ba52'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected,'pinned Verilator archive differs'
with tarfile.open(archive) as t:
 root=B/t.getmembers()[0].name.split('/')[0]
 if not root.exists():t.extractall(B,filter='data')
env=os.environ.copy()
env['PATH']='/nix/store/z81cjs7gbr38jza8a9rslfb9x0nyywn1-autoconf-2.73/bin:/nix/store/rj872hqzghsgbi6dbcs6zvwxwv44y8ll-flex-2.6.4/bin:'+env['PATH']
for cmd in [['autoconf'],['./configure','--prefix='+str(B/'verilator-5.048')],['make','-C','src','-j6','opt']]:
 subprocess.run(cmd,cwd=root,env=env,check=True)
env['VERILATOR_ROOT']=str(root)
version=subprocess.check_output([str(root/'bin/verilator'),'--version'],env=env,text=True).strip()
(R/'evidence/results/verilator-build.json').write_text(json.dumps(dict(release='v5.048',source_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),version=version,source_root=str(root),flow='autoconf; configure; make -C src -j6 opt; Flex 2.6.4',scope='local build; no global install'),indent=2)+'\n')
print(version)
