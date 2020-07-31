/*
 *  This file is part of the Frontal attack PoC.
 *
 *  Copyright (C) 2020 Ivan Puddu <ivan.puddu@inf.ethz.ch>,
 *                     Miro Haller <miro.haller@alumni.ethz.ch>,
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

/*
 * This attack uses the general structure of the SGX-Step benchmarking
 * application from Jo Van Bulck and Raoul Strackx. Moreover, we adapted
 * part of this structure to improve the measurements.
 */

#include <stdint.h>
#include <string.h>
#include <stdlib.h>

// see asm_secret_branch.S
extern void asm_secret_branch(uint8_t *do_cnt_instr, uint8_t secret, uint64_t *arr);

inline void asm_ipp(uint64_t *num1, uint64_t *num2, int size, uint64_t *res, uint8_t *do_cnt_instr) {
    __asm__ volatile(
        ".align 0x10\n"
        ".equal_end:\n"
        "    mov     %ecx, (%rdx)             # 8\n"
        "    xor     %eax, %eax               # 9\n"
        "    jmp end                         # 10\n"

        ".align 0x10\n"
        "l9_ippsCmp_BN:\n"
        "    mov     -8(%r10, %rax, 1), %rdi  # 0\n"
        "    mov     -8(%r9,  %rax, 1), %rsi  # 1\n"

        "    cmp     %rsi, %rdi               # 2\n"
        "    ja      .greater                 # 2\n"
        "    sub     $8, %rax                 # 3\n"
        "    cmp     %rsi, %rdi               # 4\n"
        "    jb      .smaller                 # 4\n"
        "    cmp     %rax, %r8                # 5\n"
        "    jnz     l9_ippsCmp_BN            # 5\n"


        // Out of the loop -> Equal path
        "    xor     %ecx, %ecx               # 6\n"
        "    jmp     .equal_end               # 7\n"
        ".align 0x8\n"
        "    jge .smaller\n"
        ".greater:\n"
        "    test    %ecx, %ecx               # 3\n"
        "    setz    %cl                      # 4\n"
        "    xor     %eax, %eax               # 5\n"
        "    movzx   %cl, %ecx                # 6\n"
        "    inc     %ecx                     # 7\n"
        "    mov     %ecx, (%rdx)             # 8\n"
        "    jmp end                         # 9\n"
            

        ".align 0x10\n"
        ".smaller:\n"
        "    test    %ecx, %ecx               # 5\n"
        "    setz    %cl                      # 6\n"
        "    xor     %eax, %eax               # 7\n"
        "    movzx   %cl, %ecx                # 8\n"
        "    inc     %ecx                     # 9\n"
        "    mov     %ecx, (%rdx)             # 10\n"
        "    jmp end                         # 11\n"
    );
end:
    return;
}

void do_asm_secret_branch(uint8_t *do_cnt_instr, uint8_t *secret_arr,
                           int secret_arr_size)
{
    int i;

    uint64_t *arr = calloc(52, sizeof(uint64_t));

    for (i = 0; i < secret_arr_size; i++) {
        asm_secret_branch(do_cnt_instr, secret_arr[i], arr);
    }
    free(arr);
}

void do_asm_ipp(uint8_t *do_cnt_instr, uint8_t *secret_arr,
                    int num_tests, int BN_size)
{
    int i;
    uint64_t *num1, *num2, res;

    num1 = calloc(BN_size, sizeof(uint64_t));
    num2 = calloc(BN_size, sizeof(uint64_t));

    for (i = 0; i < num_tests; i++)  {
        // We set num1 and num2 such that the following paths are taken in asp_ipp:
        // secret = 0 -> equal
        // secret = 1 -> bigger
        // secret = 2 -> smaller
        num1[0] = secret_arr[i] & 1;
        num2[0] = secret_arr[i] >> 1;

        // Note: This has been added here cause these registers are clobbered in the
        // asm_ipp_mock*.S assembly files. 
        asm volatile ("":::"%r9", "%r10", "%r11");
        asm_ipp( num1, num2, BN_size, &res, do_cnt_instr );
    }

    free(num1);
    free(num2);
}


void *get_asm_secret_branch_adrs( void )
{
    return asm_secret_branch;
}

void *get_asm_ipp_adrs( void )
{
    return do_asm_ipp;
}

