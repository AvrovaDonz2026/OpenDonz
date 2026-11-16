#!/usr/bin/env python3
"""Build isolated OTBN memory configuration using upstream reggen modules."""
import hashlib,json,os,pathlib,re,shutil,sys
R=pathlib.Path(__file__).resolve().parent
OT=pathlib.Path('/Users/zxy/opentitan')
def prepare():
    dst=R/'build/imem8/otbn'
    shutil.copytree(OT/'hw/ip/otbn',dst,dirs_exist_ok=True)
    p=dst/'data/otbn.hjson';s=p.read_text();old='items: "4096", // 16 kB';assert s.count(old)==1
    p.write_text(s.replace(old,'items: "2048", // 8 KiB isolated evaluation'))
    sys.path.insert(0,str(OT/'util'))
    from reggen.ip_block import IpBlock
    from reggen.gen_rtl import gen_rtl
    from reggen.gen_cheader import gen_cdefines
    block=IpBlock.from_path(str(p),[])
    assert gen_rtl(block,str(dst/'rtl'))==0
    with (dst/'data/otbn_regs.h').open('w') as f: gen_cdefines(block,f,'Isolated IMEM8 configuration','Copyright lowRISC contributors; Apache-2.0')
    p=dst/'dv/verilator/otbn_top_sim.core'
    s=p.read_text().replace('  files_otbn:\n    depend:', '  files_otbn:\n    depend:\n      - lowrisc:prim_generic:all')
    p.write_text(s)
    pkg=(dst/'rtl/otbn_reg_pkg.sv').read_text()
    assert re.search(r"OTBN_IMEM_SIZE\s*=\s*'h\s*2000;",pkg)
    assert re.search(r"OTBN_DMEM_SIZE\s*=\s*'h\s*4000;",pkg)
    # Security implementation files must remain byte-identical to pinned upstream.
    for q in (dst/'rtl').glob('*.sv'):
        if q.name not in ('otbn_reg_pkg.sv','otbn_reg_top.sv'):
            assert q.read_bytes()==(OT/'hw/ip/otbn/rtl'/q.name).read_bytes(),q
    changed=[]
    for q in sorted(dst.rglob('*')):
        if not q.is_file() or '__pycache__' in str(q):continue
        rel=q.relative_to(dst);up=OT/'hw/ip/otbn'/rel
        if not up.exists() or q.read_bytes()!=up.read_bytes():
            changed.append(dict(path=str(rel),sha256=hashlib.sha256(q.read_bytes()).hexdigest()))
    (dst.parent/'configuration.json').write_text(json.dumps(dict(upstream='2e20836f9c9787bad82c84b5ba704223f06c8890',imem_bytes=8192,dmem_bus_bytes=16384,dmem_scratch_bytes=16384,expected_macros=49,changes=changed),indent=2)+'\n')
    print(dst)
if __name__=='__main__':prepare()
