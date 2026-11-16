 .section .init,"ax"
.globl _start
_start:
 la sp, __stack_top
 la t0, __data_start
 la t1, __data_end
 la t2, __data_load
0: bgeu t0,t1,4f
 lw t3,0(t2)
 sw t3,0(t0)
 addi t0,t0,4
 addi t2,t2,4
 j 0b
4: la t0, __bss_start
 la t1, __bss_end
1: bgeu t0,t1,2f
 sw zero,0(t0)
 addi t0,t0,4
 j 1b
2: call main
3: j 3b
