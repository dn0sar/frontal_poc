#!/usr/bin/python3

import argparse
import numpy as numpy
import matplotlib
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument("-r", "--num_runs", help="number of runs of the branch", type=int, required=True)
parser.add_argument("-i", "--num_instr", help="number of pairs of (test-mov) per branch", type=int, required=True)

args = parser.parse_args()

num_runs = args.num_runs
num_instr = args.num_instr


def load_file(fname):
    data = []
    secrets = []
    iter_cycles = []
    curr_secret = 0
    with open(fname, "r") as file:
        file.readline()  # testname (ignored for now)
        file.readline()  # test details (ignored for now)
        file.readline()  # file structure
        for line in file:
            if line.startswith('-'):
                # Done iter, should now append
                data.append(iter_cycles)
                secrets.append(curr_secret)
                iter_cycles = []
            else:
                d = line.split(", ")
                iter_cycles.append(int(d[0]))
                curr_secret = int(d[1])
    return data, secrets

def split_into_instructions(data, secrets, num_instr):
    # we have to split our trace into movs and tests
    # a usual trace looks like this:
    # mov (enable measurement), cmp+jnz, optional: jz, test, mov, test, mov...
    tests = []
    movs = []
    inx_skipped = []
    for inx in range(len(secrets)):
        if (len(data[inx]) != 1 + (num_instr * 2) + (1 - secrets[inx])):
            print(f"Wrong number of instructions ({len(data[inx])}) in iteration {inx} detected.. Secret was: {secrets[inx]} ")
            inx_skipped.append(inx)
            tests.append([])
            movs.append([])
            #exit(-1)
            continue
        if secrets[inx] == 0:
            del data[inx][1]

        # They are now balanced.. 
        tests.append(data[inx][1::2])
        movs.append(data[inx][2::2])

    return tests, movs, inx_skipped


data, secrets = load_file("logs/measurements.txt")

tests, movs, skipped = split_into_instructions(data, secrets, num_instr)

num_ones = sum([x for i,x in enumerate(secrets) if i not in skipped])
num_zeros = sum([x ^ 1 for i,x in enumerate(secrets) if i not in skipped])

print(f"num runs: {num_runs}, zeros: {num_zeros}, ones: {num_ones}")

print(f"num movs: {len(movs)}, num tests: {len(tests)}")

for instr_index in range(num_instr):
    with open(f"logs/movs_{instr_index}_{num_runs}.log", "w") as file:
        
        
        file.write(f"Test name addition: pair{instr_index}\n")
        file.write(
            f"Testing instruction branch0 movq %rcx, -8(%rsp) (runs: {num_zeros}, interval: 43, part: 1/4)\n")
        for run in range(num_runs):
            if run in skipped:
                continue
            if secrets[run] == 0:
                file.write(
                    f"{movs[run][instr_index]}, 1, {secrets[run]}\n")
        file.write(
            f"Testing instruction branch1 movq %rcx, -8(%rsp) (runs: {num_ones}, interval: 43, part: 2/4)\n")
        for run in range(num_runs):
            if run in skipped:
                continue
            if secrets[run] == 1:
                file.write(
                    f"{movs[run][instr_index]}, 1, {secrets[run]}\n")

        file.write(
            f"Testing instruction branch0 test %rax, %rax (runs: {num_zeros}, interval: 43, part: 3/4)\n")
        for run in range(num_runs):
            if run in skipped:
                continue
            if secrets[run] == 0:
                file.write(
                    f"{tests[run][instr_index]}, 1, {secrets[run]}\n")
        file.write(
            f"Testing instruction branch1 test %rax, %rax (runs: {num_ones}, interval: 43, part: 4/4)\n")
        for run in range(num_runs):
            if run in skipped:
                continue
            if secrets[run] == 1:
                file.write(
                    f"{tests[run][instr_index]}, 1, {secrets[run]}\n")