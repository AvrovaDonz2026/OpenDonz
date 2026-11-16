ENTRY(_start)
MEMORY { ROM (rx) : ORIGIN = 0x00000080, LENGTH = 128K
 RAM (rw) : ORIGIN = 0x10000000, LENGTH = 16K
 NVM (rw) : ORIGIN = 0x20000000, LENGTH = 4K }
SECTIONS {
 .text : { *(.init) *(.text*) *(.rodata*) } > ROM
 .data : { __data_start = .; *(.data*) *(.sdata*) . = ALIGN(4); __data_end = .; } > RAM AT>ROM
 __data_load = LOADADDR(.data);
 .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(.sbss*) *(COMMON) . = ALIGN(4); __bss_end = .; } > RAM
 .device.key : { *(.device.key) } > NVM
 .auth.ctr : { *(.auth.ctr) } > NVM
 .attestation.cert : { *(.attestation.cert) } > NVM
 __stack_top = ORIGIN(RAM)+LENGTH(RAM);
 __process4_stack_base__ = __bss_end;
 __process4_stack_size__ = 4096;
 ASSERT(__bss_end + 4096 < __stack_top, "RAM/stack overflow")
}
