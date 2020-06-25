#!/usr/bin/python3

import argparse
import numpy as numpy

from logger import Logger

help_msgs = {
    "--num_runs":   "number of runs of the branch",
    "--num_instr":  "number of pairs of (test-mov) per branch",
    "--verbose":    "print debug output",
}

parser = argparse.ArgumentParser()
parser.add_argument("-r", "--num_runs", help=help_msgs["--num_runs"],
                    type=int, required=True)
parser.add_argument("-i", "--num_instr", help=help_msgs["--num_instr"],
                    type=int, required=True)
parser.add_argument("-v", "--verbose", help=help_msgs["--verbose"], action="store_true")

args = parser.parse_args()

num_runs    = args.num_runs
num_instr   = args.num_instr
verbose     = args.verbose

logger = Logger(parser.prog)
logger.title("Parse log file")

if verbose:
    logger.set_verbose()

def load_file(fname):
    data = []
    secrets = []
    iter_cycles = []
    curr_secret = 0
    events = ""
    with open(fname, "r") as file:
        logger.debug("Skipping: " + file.readline())  # testname (ignored for now)
        events = file.readline()
        events = ("(" + events.split("(")[1].split(")")[0] + ")") \
                 if ("events" in events) else ''

        logger.debug("Skipping: " + file.readline())  # file structure
        for line in file:
            if line.startswith('-'):
                # Done iter, should now append
                data.append(iter_cycles)
                secrets.append(curr_secret)
                iter_cycles = []
            else:
                d = [int(x) for x in line.split(", ")]
                curr_secret = d[1]
                iter_cycles.append([d[0]] + d[2:])
    return data, secrets, events

def split_into_instructions(data, secrets, num_instr):
    # we have to split our trace into movs and tests
    # a usual trace looks like this:
    # mov (enable measurement), cmp+jnz, optional: jz, test, mov, test, mov...
    tests = []
    movs = []
    inx_skipped = []
    for inx in range(len(secrets)):
        if (len(data[inx]) != 1 + (num_instr * 2) + (1 - secrets[inx])):
            logger.warning(f"Wrong number of instructions ({len(data[inx])}) in "
                           f" iteration {inx} detected.. Secret was: {secrets[inx]}")
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


data, secrets, events = load_file("logs/measurements.txt")

tests, movs, skipped = split_into_instructions(data, secrets, num_instr)

num_ones = sum([x for i,x in enumerate(secrets) if i not in skipped])
num_zeros = sum([x ^ 1 for i,x in enumerate(secrets) if i not in skipped])
num_per_secret = [num_zeros, num_ones]

logger.line(f"num runs: {num_runs}, zeros: {num_zeros}, ones: {num_ones}")

logger.line(f"num movs: {len(movs)}, num tests: {len(tests)}")

for instr_index in range(num_instr):
    with open(f"logs/movs_{instr_index}_{num_runs}.log", "w") as file:
        file.write(f"Test name addition: pair{instr_index}\n")

        for secret in range(2):
            file.write(
                f"Testing instruction branch{secret} movq %rcx, -8(%rsp) {events}"
                f"(runs: {num_per_secret[secret]}, part: {secret+1}/4)\n"
            )
            for run in range(num_runs):
                if run in skipped:
                    continue
                if secrets[run] == secret:
                    for inx, val in enumerate(movs[run][instr_index]):
                        if inx: file.write(", ")
                        file.write(f"{val}")
                    file.write("\n")

        for secret in range(2):
            file.write(
                f"Testing instruction branch{secret} test %rax, %rax {events}"
                f"(runs: {num_per_secret[secret]}, part: {secret+3}/4)\n"
            )
            for run in range(num_runs):
                if run in skipped:
                    continue
                if secrets[run] == secret:
                    for inx, val in enumerate(tests[run][instr_index]):
                        if inx: file.write(", ")
                        file.write(f"{val}")
                    file.write("\n")
