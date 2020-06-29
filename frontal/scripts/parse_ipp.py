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

import argparse
import random
import statistics
from itertools import accumulate
import numpy as np
from sklearn.cluster import KMeans
import sys

from logger import Logger


def get_path_length(ms_tuples, comb):
    length_arr = [ len(cycles) for cycles, s in ms_tuples if s == comb ]
    length_dict = {}
    for l in length_arr:
        length_dict[l] = length_dict.get(l, 0) + 1
    return length_dict


help_msgs = {
    "log_file":     "path to log file to parse",
    "--iters_num":  "Lenght of the secret byte string",
    "--verbose":        "print debug output",
}

parser = argparse.ArgumentParser()
parser.add_argument("log_file", help=help_msgs["log_file"])
parser.add_argument("-r", "--num_runs", help=help_msgs["--iters_num"],
                    type=int, default=None)
parser.add_argument("-v", "--verbose", help=help_msgs["--verbose"], action="store_true")
## This argument is here just to keep the same interface with the other parse script
parser.add_argument("-i", help=argparse.SUPPRESS, required=False)

args = parser.parse_args()
log_file_path       = args.log_file
iter_num            = args.num_runs
iter_idx            = 0
verbose             = args.verbose

logger = Logger(parser.prog)
if verbose:
    logger.set_verbose()


# Sets the configuration values for the different paths
# Note that in the equal path the target mov is not aligned the same
# as the other paths.
instr_dict = {}
#instr_dist[(secret_combination)] = [target instr inx, path, instruction description]
instr_dict[0]  = [-3, 'equal',   'mov     %ecx, (%rdx)']
instr_dict[1]  = [-2, 'bigger',  'mov     %ecx, (%rdx)']
instr_dict[2]  = [-2, 'smaller', 'mov     %ecx, (%rdx)']

# Read measurements into a list together with the true secret values
if (iter_num):
    ms_tuples = [(-1,-1)] * iter_num
else:
    ms_tuples = []

iter_info = []
iter_idx = 0

events = ''

with open(log_file_path, "r") as log_file:
    for line in log_file:
        if line[0] == '-':

            info = iter_info

            if not iter_num: ms_tuples.append([])
            ms_tuples[iter_idx] = (info, secret)
            iter_idx += 1

            iter_info = []
        elif not line[0].isdigit():
            # Check if this line contains info about events measured
            events = ("(" + line.split("(")[1].split(")")[0] + ")") if ("events" in line) else events
        else:
            line_items = [int(x) for x in line.split(", ")]
            secret = line_items[1]
            iter_info.append([line_items[0]] + line_items[2:])

if events:
    logger.debug("Found events " + events)

if (not iter_num):
    iter_num = iter_idx

if (iter_num != iter_idx):
    logger.error(f'Detected {iter_idx} out of {iter_num} iterations.\n' + \
                "Try decreasing the Is the SGX_STEP_TIMER to detect all instruction")

avgs = [0] * len(instr_dict)
for inx, comb in enumerate(instr_dict):
    lengths = get_path_length(ms_tuples, comb)
    if len(lengths) > 4:
        logger.error("Detected abnormal runs.. Try decreasing the SGX_STEP_TIMER interval.")
    if len(lengths) > 1:
        logger.warning("Detected abnormal runs.. Is the SGX_STEP_TIMER interval too low?")
    for l in lengths:
        logger.debug(
            f"Detected {l} instructions in the {instr_dict[comb][1]} path"
            f"\t({lengths[l]} occurrences)"
        )

    num_occurrences = len([1 for _, s in ms_tuples if s == comb])
    avgs[inx] = [sum( [ cycles[instr_dict[comb][0]][0] for cycles, s in ms_tuples if s == comb ] ) / num_occurrences, num_occurrences]

logger.debug('')

logger.raw("Test name addition: different_branches")

for part_num, comb in enumerate(instr_dict):
    logger.debug(
        f"Avg execution time of {instr_dict[comb][1]} path ({avgs[part_num][1]} "
        f"occurrences):\t{avgs[part_num][0]}"
    )

    logger.raw(
        f"Testing instruction {instr_dict[comb][2]} ({instr_dict[comb][1]}) "
        f"{events}(runs: {avgs[part_num][1]}, part: {part_num + 1}/{len(instr_dict)})"
    )
    for cy, s in ms_tuples:
        #s1, s2 = s
        #if (not s1 and not s2): s1, s2 = (True, True)
        if s == comb:
            for inx, val in enumerate(cy[instr_dict[comb][0]]):
                if inx: logger.raw(", ", end='')
                logger.raw(f"{val}", end='')
            logger.raw('')

if (abs(avgs[0][0] - avgs[1][0]) > 20) or (abs(avgs[0][0] - avgs[2][0]) > 20):
    logger.line(
        "The attacker can use the frontal attack to exploit this run of "
        "the code."
    )
else:
    logger.line(
        "The attacker cannot exploit this run of the code with the frontal attack."
    )
