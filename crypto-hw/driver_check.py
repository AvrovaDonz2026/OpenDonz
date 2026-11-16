#!/usr/bin/env python3
"""Compile official HMAC DIF and run a real driver MMIO contract smoke test."""
import os,pathlib,subprocess,sys
R=pathlib.Path(__file__).resolve().parent;OT=pathlib.Path('/Users/zxy/opentitan');B=R/'build/driver';B.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(OT/'util'))
from reggen.ip_block import IpBlock
from reggen.gen_cheader import gen_cdefines
h=B/'hw/top/hmac_regs.h';h.parent.mkdir(parents=True,exist_ok=True)
with h.open('w') as f:gen_cdefines(IpBlock.from_path(str(OT/'hw/ip/hmac/data/hmac.hjson'),[]),f,'Apache-2.0','Copyright lowRISC contributors')
a=B/'sw/device/lib/dif/autogen';a.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,PYTHONPATH=str(OT/'util'))
subprocess.run([sys.executable,str(OT/'util/autogen_dif.py'),'-i',str(OT/'hw/ip/hmac/data/hmac.hjson'),'-o',str(a)],env=env,check=True)
dt=B/'hw/top/dt/hmac.h';dt.parent.mkdir(parents=True,exist_ok=True);dt.write_text('/* Host-only type adapter: no device-tree implementation claimed. */\ntypedef unsigned dt_hmac_t; typedef unsigned dt_hmac_irq_t;\n')
source=B/'driver_test.c';source.write_text(r'''#include <assert.h>
#include <stdio.h>
#include "sw/device/lib/dif/dif_hmac.h"
#include "hw/top/hmac_regs.h"
static uint32_t regs[2048];
extern bool mmio_region_get_bit32(mmio_region_t,ptrdiff_t,uint32_t);
extern void mmio_region_nonatomic_set_bit32(mmio_region_t,ptrdiff_t,uint32_t);
uint32_t mmio_region_read32(mmio_region_t base,ptrdiff_t off){(void)base;return regs[off/4];}
void mmio_region_write32(mmio_region_t base,ptrdiff_t off,uint32_t val){(void)base;regs[off/4]=val;}
void mmio_region_write8(mmio_region_t base,ptrdiff_t off,uint8_t val){(void)base;regs[off/4]=val;}
int main(void){
 dif_hmac_t h={0};dif_hmac_transaction_t t={.message_endianness=kDifHmacEndiannessLittle,.digest_endianness=kDifHmacEndiannessLittle,.digest_size=kDifSHA256,.key_length=kDifHMACKey256};
 assert(dif_hmac_mode_sha256_start(NULL,t)==kDifBadArg);
 assert(dif_hmac_mode_sha256_start(&h,t)==kDifOk);
 assert(regs[HMAC_CFG_REG_OFFSET/4]&(1u<<HMAC_CFG_SHA_EN_BIT));
 assert(!(regs[HMAC_CFG_REG_OFFSET/4]&(1u<<HMAC_CFG_HMAC_EN_BIT)));
 assert(regs[HMAC_CMD_REG_OFFSET/4]&(1u<<HMAC_CMD_HASH_START_BIT));
 size_t sent=0;assert(dif_hmac_fifo_push(&h,"abc",3,&sent)==kDifOk);assert(sent==3);
 assert(dif_hmac_process(&h)==kDifOk);assert(regs[HMAC_CMD_REG_OFFSET/4]&(1u<<HMAC_CMD_HASH_PROCESS_BIT));
 dif_hmac_digest_t d;assert(dif_hmac_finish(&h,false,&d)==kDifUnavailable);
 regs[HMAC_INTR_STATE_REG_OFFSET/4]=1u<<HMAC_INTR_STATE_HMAC_DONE_BIT;regs[HMAC_STATUS_REG_OFFSET/4]=1u<<HMAC_STATUS_FIFO_EMPTY_BIT;
 for(int i=0;i<8;i++)regs[HMAC_DIGEST_0_REG_OFFSET/4+i]=0x12340000u+i;
 assert(dif_hmac_finish(&h,false,&d)==kDifOk);assert(d.digest[0]==0x12340007);
 puts("PASS official HMAC DIF compile/MMIO contract; no hardware KAT");return 0;
}
''')
cmd=['clang','-std=c11','-O2','-ffunction-sections','-fdata-sections','-I'+str(B),'-I'+str(OT),str(source),str(OT/'sw/device/lib/dif/dif_hmac.c'),'-Wl,-dead_strip','-o',str(B/'driver_test')]
subprocess.run(cmd,check=True);subprocess.run([str(B/'driver_test')],check=True)
