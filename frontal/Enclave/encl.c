/*
 *  This file is part of the SGX-Step enclave execution control framework.
 *
 *  Copyright (C) 2017 Jo Van Bulck <jo.vanbulck@cs.kuleuven.be>,
 *                     Raoul Strackx <raoul.strackx@cs.kuleuven.be>
 *
 *  SGX-Step is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  SGX-Step is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with SGX-Step. If not, see <http://www.gnu.org/licenses/>.
 */

/* Modified by Ivan Puddu <ivan.puddu@inf.ethz.ch> on 20.02.2020 */

#include <stdint.h>
#include <string.h>
#include <stdlib.h>

// see asm_secret_branch.S
extern void asm_secret_branch(uint8_t *do_cnt_instr, uint8_t secret, uint64_t *arr);

extern void asm_ipp(uint64_t *num1, uint64_t *num2, int size, uint64_t *res, uint8_t *do_cnt_instr);

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
    return asm_ipp;
}

