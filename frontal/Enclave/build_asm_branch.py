#!/usr/bin/python3
import string
import sys

if (len(sys.argv) != 4):
    print("usage: build_asm.py <inst_slide_len> <align1> <align2>")
    print("example:\n\tbuild_asm.py 52 12 15")
    exit(1)

NR_OF_INST = int(sys.argv[1])
ALIGN1 = sys.argv[2]
ALIGN2 = sys.argv[3]

prepare = "\ttest %rax, %rax\n"
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
