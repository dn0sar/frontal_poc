/*
 *  This file is part of the Frontal attack PoC.
 *
 *  Copyright (C) 2020 Ivan Puddu <ivan.puddu@inf.ethz.ch>,
 *                     Moritz Schneider <moritz.schneider@inf.ethz.ch>
 *
 *  The Frontal attack PoC is free software: you can redistribute it
 *  and/or modify it under the terms of the GNU General Public License
 *  as published by the Free Software Foundation, either version 3 of
 *  the License, or (at your option) any later version.
 *
 *  The Frontal attack PoC is distributed in the hope that it will
 *  be useful, but WITHOUT ANY WARRANTY; without even the implied
 *  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
 *  See the GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with the Frontal attack PoC.
 *  If not, see <http://www.gnu.org/licenses/>.
 */

    .text
    .global asm_ipp
    .align 0x1000 /* 4KiB */
    .type asm_ipp, @function
    .type l9_ippsCmp_BN, @function

# To run this function we need to give the following parameters:
# uint64_t * num1, uint64_t * num2, uint64_t *res, do_cnt_instr

# Registers used by the function
# rdi, rsi, rdx, rcx, rax, r9, r10, r11
# Registers to declare as clobbers in C: r9, r10, r11
asm_ipp:
    mov %rdi, %r10        # r10 -> base of num1 from the end
    mov %rsi, %r9         # r9  -> base of num2 from the end
    mov %rdx, %rax
    shl $3, %rax          # rax -> size of the array * 8        
    mov %rcx, %rdx        # rdx is the address of the result
    mov %r8,  %r11        # r11 is the shared variable to sync the recording of instructions
    mov $0, %r8           # r8 is used just to use the same instruction size in the cmp below


    movb $1, (%r11)       # Start recording instructions
    call l9_ippsCmp_BN
    movb $0, (%r11)       # Stop recording instructions
    ret


# Note: each instruciton is aligned the same way modsulo 16
# as the original l9_ippsCmp_BN in the IPP prebuilt library v2.9
.align 0x10
.equal_end:
    mov     %ecx, (%rdx)             # 8
    xor     %eax, %eax               # 9
    ret                              # 10

.align 0x10
l9_ippsCmp_BN:
    mov     -8(%r10, %rax, 1), %rdi  # 0
    mov     -8(%r9,  %rax, 1), %rsi  # 1

    cmp     %rsi, %rdi               # 2
    ja      .greater                 # 2
    sub     $8, %rax                 # 3
    cmp     %rsi, %rdi               # 4
    jb      .smaller                 # 4
    cmp     %rax, %r8                # 5
    jnz     l9_ippsCmp_BN            # 5


# Out of the loop -> Equal path
    xor     %ecx, %ecx               # 6
    jmp     .equal_end               # 7
.align 0x8
    jge .smaller
.greater:
    test    %ecx, %ecx               # 3
    setz    %cl                      # 4
    xor     %eax, %eax               # 5
    movzx   %cl, %ecx                # 6
    inc     %ecx                     # 7
    mov     %ecx, (%rdx)             # 8
    ret                              # 9
    

.align 0x10
.smaller:
    test    %ecx, %ecx               # 5
    setz    %cl                      # 6
    xor     %eax, %eax               # 7
    movzx   %cl, %ecx                # 8
    inc     %ecx                     # 9
    mov     %ecx, (%rdx)             # 10
    ret                              # 11

    /* 4KiB space; ensures that next page after code has no other code in it
       to make sure no false-positive page accesses happen when we are mesuring*/
    .space 0x1000