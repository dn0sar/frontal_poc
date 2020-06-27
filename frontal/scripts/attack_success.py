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

#--------------------------------------------------------------------------------
# This script parses the output of the frontal attack PoC
# and outputs the precision (how many branches were detected correctly)
#--------------------------------------------------------------------------------

import argparse
import random
import statistics
from itertools import accumulate
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import mutual_info_score
from scipy.stats.stats import pearsonr,spearmanr

def calc_mutual_information(x, y, bins):
    c_xy = np.histogram2d(x, y, bins)[0]
    mi = mutual_info_score(None, None, contingency=c_xy)
    return mi

# sep_index should start from 1 (0 is the empty array)
def hit_rate_mirror(sorted_secrets, sep_inx, val):
    hit_left = len([s for s in sorted_secrets[:sep_inx] if s == val])
    hit_right = len([s for s in sorted_secrets[-sep_inx:] if s == (1 - val)])
    hit = hit_left + hit_right
    return (hit / (sep_inx*2)) * 100

def hit_rate_sep(sorted_secrets, sep_inx):
    fast = 1
    hit_left = len([s for s in sorted_secrets[:sep_inx] if s == fast])
    hit_right = len([s for s in sorted_secrets[sep_inx:] if s == 1 - fast])
    tot_hit = hit_left + hit_right
    if (tot_hit < len(secrets) // 2):
        tot_hit = len(secrets) - tot_hit
        fast = 1 - fast
    return ((tot_hit) / len(secrets)) * 100, fast

def kmeans_hit_rate(sorted_cycles, sorted_secrets):
    cycles_array = np.array(sorted_cycles).reshape(-1, 1)
    kmeans = KMeans(n_clusters=2, random_state=None).fit(cycles_array)
    ## Since the cycles are sorted assume first point belongs to the if branch (i.e. secret = 1)
    hit_count = len([x for inx, x in enumerate(kmeans.labels_) if x == sorted_secrets[inx]])
    ## If the labels have been assigned in the other way we switch the hit_count
    #if (hit_count < len(sorted_cycles) // 2):
    #    hit_count = len(sorted_cycles) - hit_count
    return hit_count / len(sorted_cycles) * 100

def __find_empirical_best(secrets):
    acc = list(accumulate(secrets))
    tot_secrets = len(secrets)
    tot_ones = acc[-1]
    constant_part = tot_secrets - tot_ones - 1
    best_hit = 0
    values = [2 * ones - inx  for inx, ones in enumerate(acc)]
    best_inx = max(range(len(values)), key=values.__getitem__)
    return (values[best_inx] + constant_part) / tot_secrets * 100, best_inx + 1

def find_empirical_best(secrets):
    b, i = __find_empirical_best(secrets)
    # Maybe the loop timings are better in the opposite direction
    binv, iinv = __find_empirical_best([abs(x - 1) for x in secrets])
    return (b, i) if b > binv else (binv, iinv)

def guess_by_median_multiple(iter_timings, start_inx, num, direction = 1):
    same_behaviour_dist = 4
    even_times = [iter_timings[i] for i in range(start_inx, start_inx + same_behaviour_dist * num, same_behaviour_dist)]
    start_inx += 2
    odd_times  = [iter_timings[i] for i in range(start_inx, start_inx + same_behaviour_dist * num, same_behaviour_dist)]
    med_even = statistics.median(even_times)
    med_odd = statistics.median(odd_times)
    return (1 - direction) if (med_even < med_odd) else direction


def guess_by_zig_zag(iter_timings, start_inx, num):
    pattern = [0]*num
    p_inx = 0
    for i in range(start_inx + 2, start_inx + (num + 1)*2, 2):
        pattern[p_inx] = -1 if (iter_timings[i - 2] > iter_timings[i]) else 1
        p_inx += 1
    longest_seq = -1
    longest_start = -1
    for i in range(len(pattern)):
        for j in range(i, len(pattern)):
            if -1 < sum(pattern[i:j]) < 1 and (longest_seq < (j - i + 1)):
                longest_seq = j - i + 1
                longest_start = i
    # print('Longest seq was: ' + str(longest_seq))
    res = 0 if ((longest_start % 2 == 0) and pattern[longest_start] == -1) else 1
    return res if (longest_seq >= (num * 9/10) ) else 2

parser = argparse.ArgumentParser()
parser.add_argument("log_file", help="Path to log file to parse")
parser.add_argument("secret_file", help="Path to secret file to validate the log file")
parser.add_argument("-n", "--iters_num", type=int, default=None, help="Lenght of the secret byte string")
parser.add_argument("-s", "--test_size", type=int, default=0, required=True,
                    help="Number of instructions to be expected in one iteration")
parser.add_argument("-j", "--jump_inx", type=int, default=1,
                    help="Index of the jump instruction so the offset can be added properly if the jmp was counted")
parser.add_argument("-c", "--correlate_num", type=int, default=None,
                    help="How many instructions should be used to correlate the result after the first index")    #+ \
#                          "This is usually 1 if the jump was before the measured instruction")
parser.add_argument("-o", "--output", default=False,
                    help="Output the percentages into this file")
parser.add_argument("-g", "--global_run", default=False, action='store_true',
                    help="The input file contains only one number per run")
inx_group = parser.add_mutually_exclusive_group(required=True)
inx_group.add_argument("-i", "--measure_inx", type=int, default=None,
                    help="Index of the instruction to be used to discriminate branches")
inx_group.add_argument("-a", "--all_inx", default=False, action='store_true',
                    help="Analyze all indexes to see which ones are best predictors")


args = parser.parse_args()
log_file_path       = args.log_file
secret_file_path    = args.secret_file
iter_num            = args.iters_num
measure_inx         = args.measure_inx
jump_inx            = args.jump_inx
measure_all         = args.all_inx
test_size           = args.test_size
correlate_num       = args.correlate_num
iter_idx            = 0
global_run          = args.global_run

if global_run:
    test_size = 1

output_file         = args.output

tot_cycles  = 0
hit_cnt     = 0

# Read measurements into a list together with the true secret value
if (iter_num):
    ms_tuples = [(-1,-1)] * iter_num
else:
    ms_tuples = []
# +1 because sometimes we count also the jmp instruction
iter_cycles = []

iter_idx = 0
skipped = 0

with open(log_file_path, "r") as log_file:
    with open(secret_file_path, "r") as secret_file:
        for line in log_file:
            if (global_run and line[0].isdigit()):
                iter_cycles.append(int(line.split(", ")[0]))
                line = '-'
            if line[0] == '-':
                to_skip = (len(iter_cycles) < test_size or len(iter_cycles) > test_size + 1)
                if (iter_num and iter_idx == iter_num):
                    # Too many iterations were present
                    # Terminate parsing and show error later
                    iter_idx += 1
                    break
                if (len(iter_cycles) == test_size + 1):
                    del iter_cycles[jump_inx]
                cycles = iter_cycles

                secret = secret_file.readline()
                if not to_skip:
                    if not iter_num: ms_tuples.append([])
                    ms_tuples[iter_idx] = (cycles, int(secret))
                    iter_idx += 1
                else:
                    print("Iteration skipped. Count was: " + str(len(iter_cycles)))
                    skipped += 1

                iter_cycles = []
            elif not line[0].isdigit():
                continue
            else:
                iter_cycles.append(int(line.split(", ")[0]))

if (not iter_num):
    iter_num = iter_idx

print(f'Detected {iter_idx} iterations')

if skipped > 0:
    print(f'Error: counted an unexpected number of instructions in {skipped} iteration' + ('s' if skipped > 1 else '') + '.')
    print(f'Please check if the size of one iteration is actually {test_size}.')
    print('If not re-run, with the correct size. Otherwise the trace is inconsistent.')
    del ms_tuples[-skipped:]


if skipped == iter_num:
    print('Aborting..')
    exit(-1)

if skipped > 0:
    print('Inconsistent runs have been discarded..')

if (iter_idx + skipped != iter_num):
    print(f"ERROR: Number of parsed iterations does not match the "
          "expected number ({iter_num})")
    exit(-1)

print('Done parsing..')

check_inxes = range(test_size) if measure_all else [measure_inx]

for inx in check_inxes:
    # Sort the tuples by the measurement
    # ms_tuples.sort(key=lambda t:t[0][inx])
    cycles  = [c[inx] for c, _ in ms_tuples]
    secrets = [s for _, s in ms_tuples]
    cor_coef = np.corrcoef(cycles, secrets)
    print(f"pearsonr (numpy):\t{cor_coef[0,1]}")

    cor_coef = pearsonr(cycles, secrets)
    print(f"pearsonr (scipy):\t{cor_coef[0]}")
    print(f"\tp-value:\t{cor_coef[1]}")

    # spearmanr
    cor_coef = spearmanr(cycles, secrets)
    print(f"spearmanr:\t\t{cor_coef[0]}")
    print(f"\tp-value:\t{cor_coef[1]}")

    nr_bins = max(cycles) - min(cycles)
    #mutual information
    mutual_info = calc_mutual_information(cycles, secrets, nr_bins)
    print(f"Mutual Information:\t{mutual_info}")

print("Trying to correlate multiple timings..")

results = []

for inx in check_inxes:
    # Sort the tuples by the measurement
    ms_tuples.sort(key=lambda t:t[0][inx])
    cycles  = [c[inx] for c, _ in ms_tuples]
    secrets = [s for _, s in ms_tuples]


    kmeans_hit         = kmeans_hit_rate(cycles, secrets)
    hit_best, inx_best = find_empirical_best(secrets)

    mean_cycles        = sum(cycles) / iter_num
    if output_file is False:
        print('\n' +
              f'Instr index:     {inx}')
        print(f"Mean:            {mean_cycles}")
        print(f"Best threshold:  {cycles[inx_best - 1]}")

    # Guess the first half as having executed the fast branch and the
    # the second half the slow branch
    hit_rate_s, direction = hit_rate_sep(secrets, iter_num // 2)
    if output_file is False:
        print("\n" +
              f'Hit rate half:   {hit_rate_s}%')
    #   print(f"Kmeans hit rate: {kmeans_hit}%")
        print(f"Hit best:        {hit_best}%")
        print("The fast branch was the " + ('else' if direction else 'first') + " branch")
    results.append(hit_rate_s)

if output_file is not False:
    print(f'saving results to {output_file}...')
    np.savetxt(output_file, np.array(results))

print('')


# The following only makes sense only if there are at least (correlate_num + 1) instructions in the same branch to compare
if (correlate_num and test_size - inx > correlate_num):
    guessed_bits = [guess_by_median_multiple(ms_tuples[iter_inx][0], inx, correlate_num, direction) for iter_inx in range(iter_num)]
    hit_rate_median = (len([1 for x in range(iter_num) if guessed_bits[x] == ms_tuples[x][1]]) / iter_num) * 100
    print(f'Hit rate correlating the median of {correlate_num * 2} instructions: {hit_rate_median}%')
