#include <stdint.h>
#include <stddef.h>
#include "chopstx.h"
#include "usb-hid.h"
#include "u2f-hid.h"
#define REG(a) (*(volatile uint32_t *)(uintptr_t)(a))
/* External-controller mailbox CONTRACT. No corresponding RTL yet. Fail closed. */
#define BASE 0x40000000u
/* +0x18 is a wrapping 32-bit MICROSECOND timer (upstream HID timeout unit). */
uint8_t blink_is_on;
static unsigned pressed;
void *memcpy(void *d,const void *s,size_t n) { unsigned char *a=d; const unsigned char *b=s; while(n--) *a++=*b++; return d; }
void *memset(void *d,int c,size_t n) { unsigned char *a=d; while(n--) *a++=c; return d; }
int memcmp(const void *a,const void *b,size_t n) { const unsigned char *x=a,*y=b; while(n--) { if(*x!=*y) return *x-*y; ++x;++y; } return 0; }
__attribute__((noreturn)) static void halt(void) { for(;;) __asm__ volatile("wfi"); }
int random_gen(void *index,uint8_t *p,size_t n) { (void)index; while(n--) { if(!(REG(BASE+0x20)&1)) return -1; *p++=REG(BASE+0x24); } return 0; }
void random_bytes_free(void *p) { (void)p; }
void flash_erase_page(uintptr_t a) { REG(BASE+0x30)=a; REG(BASE+0x34)=1; while(REG(BASE+0x34)&1){} if(REG(BASE+0x34)&2) halt(); }
void flash_write(uintptr_t a,const uint8_t *p,unsigned n) { while(n--) { REG(BASE+0x30)=a++; REG(BASE+0x38)=*p++; REG(BASE+0x34)=4; while(REG(BASE+0x34)&4){} if(REG(BASE+0x34)&2) halt(); } }
int user_presence_get(void) { if(REG(BASE+0x10)&1) pressed=1; return pressed; }
void user_presence_reset(void) { pressed=0; REG(BASE+0x10)=1; }
int hid_send(struct usb_hid *h,uint8_t *p,uint16_t n) { (void)h; if(n!=64)return -1; while(!(REG(BASE)&2)){} for(unsigned i=0;i<n;i++) REG(BASE+8)=p[i]; REG(BASE+12)=2; return n; }
int hid_recv(struct usb_hid *h,uint8_t *p,uint16_t n,uint32_t timeout) { (void)h; uint32_t start=REG(BASE+0x18); while(!(REG(BASE)&1)) if((uint32_t)(REG(BASE+0x18)-start)>=timeout)return -1; for(unsigned i=0;i<n;i++)p[i]=REG(BASE+4); REG(BASE+12)=1; return n; }
chopstx_t chopstx_create(unsigned priority,uint32_t stack,uint32_t size,void *(*f)(void *),void *a) { (void)priority;(void)stack;(void)size; f(a); halt(); return 0; }
int main(void) { if(REG(BASE+0x3c)!=0x55324631)halt(); u2f_hid_open((struct usb_hid *)1); halt(); }
