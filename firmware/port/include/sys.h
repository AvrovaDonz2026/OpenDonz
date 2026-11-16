#include <stdint.h>
void flash_erase_page(uintptr_t);
void flash_write(uintptr_t,const uint8_t *,unsigned);
