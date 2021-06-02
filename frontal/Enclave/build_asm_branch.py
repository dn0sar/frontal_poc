#!/usr/bin/python3

#   This file is part of the Frontal attack PoC.
#
#   Copyright (C) 2020 Ivan Puddu <ivan.puddu@inf.ethz.ch>,
#                      Miro Haller <miro.haller@alumni.ethz.ch>,
#                      Moritz Schneider <moritz.schneider@inf.ethz.ch>
#
#   The Frontal attack PoC is free software: you can redistribute it
#   and/or modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.
#
#   The Frontal attack PoC is distributed in the hope that it will
#   be useful, but WITHOUT ANY WARRANTY; without even the implied
#   warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#   See the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with the Frontal attack PoC.
#   If not, see <http://www.gnu.org/licenses/>.



import string
import sys

if (len(sys.argv) != 4):
    print("usage: build_asm.py <inst_slide_len> <align1> <align2>")
    print("example:\n\tbuild_asm.py 52 12 15")
    exit(1)

NR_OF_INST = int(sys.argv[1])
ALIGN1 = sys.argv[2]
ALIGN2 = sys.argv[3]

## Any 3 bytes long instruction as prepare instruction will produce the same effects.
## For instance, a 'test register to register' can also be used instead of a 3 bytes add
#prepare = "\ttest %rax, %rax\n"
prepare = "\tadd %rax, %rax\n"
asm_code = "\tmov %rcx, -8(%rsp)\n"

template = string.Template(
    '''/* ====== auto generated asm code from Python script ======= */

    .text
    .global asm_secret_branch, asm_secret_branch_end
    .align 0x1000 /* 4KiB */
    .type asm_secret_branch, @function

asm_secret_branch:
    movb $$1, (%rdi) // Start counting instructions
    test %rsi, %rsi
    jnz .elseBranch
    jz .ifbranch

.align 0x10
.space $space1
.ifbranch:
$asmCode
    movb $$0, (%rdi) // Stop counting instructions
    ret
.align 0x10
.space $space2
.elseBranch:
$asmCode
    movb $$0, (%rdi) // Stop counting instructions
asm_secret_branch_end:
    ret

    /* 4KiB space; ensures that next page after code has no other code in it
       to make sure no false-positive page accesses happen when we are mesuring*/
    .space 0x1000
''')

asm = ""

for i in range(NR_OF_INST):
    asm += prepare
    asm += asm_code  # .format(8*i)

with open("asm_secret_branch.S", 'w') as asm_file:
    code = template.substitute(
        asmCode=asm,
        script="build_asm_branch.py",
        space1=hex(int(ALIGN1)),
        space2=hex(int(ALIGN2)))
    asm_file.write(code)
