#!/usr/bin/python3

#   This file is part of the Frontal attack PoC.
#
#   Copyright (C) 2020 Ivan Puddu <ivan.puddu@inf.ethz.ch>,
#                      Miro Haller <miro.haller@alumni.ethz.ch>
#                      Moritz Schneider <moritz.schneider@inf.ethz.ch>,
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


def get_path_length(ms_tuples, comb):
    length_arr = [ len(cycles) for cycles, s in ms_tuples if s == comb ]
    length_dict = {}
    for l in length_arr:
        length_dict[l] = length_dict.get(l, 0) + 1
    return length_dict


parser = argparse.ArgumentParser()
parser.add_argument("log_file", help="Path to log file to parse")
parser.add_argument("-n", "--iters_num", type=int, default=None, help="Lenght of the secret byte string")

args = parser.parse_args()
log_file_path       = args.log_file
iter_num            = args.iters_num
iter_idx            = 0

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

print("Found events " + events, file=sys.stderr)

if (not iter_num):
    iter_num = iter_idx

print(f'Detected {iter_idx} iterations\n', file=sys.stderr)


avgs = [0] * len(instr_dict)
for inx, comb in enumerate(instr_dict):
    lengths = get_path_length(ms_tuples, comb)
    for l in lengths:
        print(f'Detected {l} instructions in the {instr_dict[comb][1]} path\t({lengths[l]} occurrences)', file=sys.stderr)

    num_occurrences = len([1 for _, s in ms_tuples if s == comb])
    avgs[inx] = [sum( [ cycles[instr_dict[comb][0]][0] for cycles, s in ms_tuples if s == comb ] ) / num_occurrences, num_occurrences]

print('', file=sys.stderr)

print("Test name addition: different_branches")

for part_num, comb in enumerate(instr_dict):
    print(f'Avg execution time of {instr_dict[comb][1]} path ({avgs[part_num][1]} occurrences):\t{avgs[part_num][0]}', file=sys.stderr)

    print(f"Testing instruction {instr_dict[comb][2]} ({instr_dict[comb][1]}) {events}(runs: {avgs[part_num][1]}, part: {part_num + 1}/{len(instr_dict)})")
    for cy, s in ms_tuples:
        #s1, s2 = s
        #if (not s1 and not s2): s1, s2 = (True, True)
        if s == comb:
            for inx, val in enumerate(cy[instr_dict[comb][0]]):
                if inx: print(", ", end='')
                print(f"{val}", end='')
            print('\n', end='')

if (abs(avgs[0][0] - avgs[1][0]) > 20) or (abs(avgs[0][0] - avgs[2][0]) > 20):
    print("\n!!!! The attacker can use the frontal attack to exploit this run of the code.", file=sys.stderr)
else:
    print("\nThe attacker cannot exploit this run of the code with the frontal attack.", file=sys.stderr)