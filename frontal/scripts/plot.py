#!/usr/bin/python3

import re
# Next to lines are to use matplotlib without X server (display)
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import argparse
from scipy.stats import norm
from os.path import isfile

from logger import Logger

# Constant configuration variables
FILTER_OUTLIERS         = True
STD_DIST_FACTOR         = 4
STD_DIST_FACTOR_EVENTS  = 4

help_msgs = {
    "log_file":         "path to log file to parse",
    "--x_axis":         "set a fixed x axis (to make it easier to compare plots)",
    "--output_folder":  "path to folder for the produced plots",
    "--no_gaussian":    "do not fit a gaussian distribution on the plots",
    "--verbose":        "print debug output",
}
parser = argparse.ArgumentParser()
parser.add_argument("log_file", help=help_msgs["log_file"])
parser.add_argument("-x", "--x_axis", nargs=2, metavar=("x_min", "x_max"),
                    help=help_msgs["--x_axis"], type=int)
parser.add_argument("-o", "--output_folder", help=help_msgs["--output_folder"],
                    default="./plots")
parser.add_argument("-g", "--no_gaussian", help=help_msgs["--no_gaussian"],
                    default=False, action="store_false")
parser.add_argument("-v", "--verbose", help=help_msgs["--verbose"], action="store_true")

args = parser.parse_args()

data_file_path          = args.log_file
data_file_path_parts    = data_file_path.rsplit('/', 1)
data_file_name          = data_file_path_parts[-1]
add_gaussian            = not args.no_gaussian
plot_folder             = args.output_folder
verbose                 = args.verbose
plot_events             = False

logger = Logger(parser.prog)
if verbose:
    logger.set_verbose()

logger.title("Start plotting")

if args.x_axis:
    x_axis      = args.x_axis
    x_range     = x_axis[1] - x_axis[0]
    nr_of_bins  = x_range // 2
    xvals       = np.linspace(x_axis[0], x_axis[1], 20 * x_range)

# helper function
def format_stats(mean, std):
    return (r' | $\mu \approx %.0f$' % (mean, )) \
            + (r', $\sigma \approx %.0f$' % (std, ))

def filter_list(mean, std, ls, factor = STD_DIST_FACTOR):
    return [elem for elem in ls
                    if abs(elem - mean) <= factor * std]


logger.line("- Start parsing log file")

total_instr = 0

with open(data_file_path, "r") as data_file:
    line    = data_file.readline()

    # Get test annotation if there is one
    match = re.search("addition: (.*)", line)
    if (match == None):
        addition = ""
    else:
        addition    = match.groups()[0]
        addition_parts = addition.split()
        addition    = addition_parts[0].strip() if len(addition_parts) > 0 else ''
        title_addition = ''
        if len(addition_parts) > 1:
            title_addition = addition_parts[1]
        line        = data_file.readline()

    # Parse instructions
    pattern     = ("instruction (.+) (?:\(events: (.+)\))*?\(runs: ([0-9]+)")
                  #", interval: ([0-9]+), part: ([0-9]+)/([0-9]+)")
        
    instrs          = []
    data            = []
    events_names    = []
    events          = []
    page_border_idx = []
    nr_events       = 0
    nr_of_parts     = 0
    old_page_nr     = 1
    
    while (line != ""):
        match   = re.search(pattern, line)
        if (match == None):
            logger.error("Wrong number of instructions!")


        groups          = match.groups()
        runs            = int(groups[2]) 
        plot_events     = plot_events or groups[1]

        instrs.append(groups[0])
        total_instr += runs

        if plot_events:
            events_names.append(groups[1].split(" "))
            nr_events       = len(events_names[-1])
            events.append([])
            [events[nr_of_parts].append([]) for _ in range(nr_events)]
        data.append([])
        page_border_idx.append([])

        for i in range(runs):
            msr_str = data_file.readline().split(", ")
            cycles  = int(msr_str[0])

            data[nr_of_parts].append( cycles )
            [ events[nr_of_parts][ev].append(int(msr_str[ev + 1])) for ev in range(nr_events) ]

        logger.line(f"\t- Parsed log for instruction \"{groups[0]}\"")

        nr_of_parts += 1;
        line         = data_file.readline()

logger.line("- Finished parsing log file")

## Calculate mean, standard deviation and remove outliers if needed
means       = []
std_devs    = []
prep_stats  = [[]] * nr_of_parts
event_stats = []

for i in range(nr_of_parts):
    means.append( np.mean(data[i]) )
    std_devs.append( np.std(data[i]) )

    if FILTER_OUTLIERS:
        data[i] = filter_list(means[i], std_devs[i], data[i])
        if plot_events:
            for ev, _ in enumerate(events[i]):
                ev_mean = np.mean(events[i][ev])
                ev_std  = np.std(events[i][ev])
                event_stats.append((ev_mean, ev_std))
                events[i][ev] = filter_list(ev_mean, ev_std, events[i][ev])

    if not args.x_axis:
        # Set dynamic x coordinates if x_min was not given
        x_axis_min  = min(min(data)) - int(max(std_devs) * STD_DIST_FACTOR)
        x_axis_max  = max(max(data)) + int(max(std_devs) * STD_DIST_FACTOR)
        x_range     = x_axis_max - x_axis_min
        nr_of_bins  = x_range // 2
    
        x_axis  = (x_axis_min, x_axis_max)
        xvals   = np.linspace(x_axis_min, x_axis_max, 20 * x_range)

    # Warn if some data is outside the plotted range
    if x_axis[0] > min(data[i]) or x_axis[1] < max(data[i]):
        logger.warning(f"Some data (range ({min(data[i])}, {max(data[i])})) is outside "
                       f"the plotted x range {x_axis}!")

if FILTER_OUTLIERS:
    filtered_instr = total_instr - sum(len(x) for x in data)
    logger.line("- Filtered {} outliers (from {} data points) out".format(
            filtered_instr, total_instr ))
else:
    logger.line("- Filtering outliers is disabled")

## Make unique labels for legend
labels          = []
prep_labels     = []
events_labels   = []
instrs_set      = {instr.split(" ", 1)[0] for instr in instrs}
instrs_set_len  = len(instrs_set)

for i in range(nr_of_parts):
    instr_name = instrs[i]

    instr_label = instr_name.replace("$", "\\$")
    if add_gaussian:
        instr_label += format_stats(means[i], std_devs[i])
    labels.append(instr_label)

    if plot_events: 
        part_labels = []
        for ev_nr in range(len(events[i])):
            # TODO: Parse from the file the event name
            part_labels.append(f"{events_names[i][ev_nr]} instr {i}") 
        events_labels.append(part_labels)

plural = ""
if (instrs_set_len > 1):
    plural = "s"

if plot_events:
    fig, axes   = plt.subplots(nrows = 2, figsize=(14,10), dpi=200)
    ax          = axes[0]
else:
    fig, ax     = plt.subplots(figsize=(9,5), dpi=200)

# Plot data
default_colors  = plt.rcParams['axes.prop_cycle'].by_key()['color']
bar_all_means   = []

for data_idx in range(nr_of_parts):
    d = data[data_idx]

    bins_y, _, _ = ax.hist(d, nr_of_bins, 
                            range=x_axis, histtype='stepfilled', 
                            label=labels[data_idx],
                            alpha=0.3, color=default_colors[data_idx])

    # Fit normal distribution to result
    norm_mean, norm_std = norm.fit(d)

    # Ensure that std != 0 otherwise we cannot plot
    if (norm_std == 0):
        norm_std = 1e-4

    norm_fn             = norm.pdf(xvals, norm_mean, norm_std)
    # Scale height to histogram height
    norm_fn            *= np.max(bins_y) / np.max(norm_fn)
    if add_gaussian:
        ax.plot(xvals, norm_fn, linewidth=.75, 
                linestyle='dashed', color=default_colors[data_idx])

    if plot_events:
        for ev in range (len(events[data_idx])):
            axes[1].hist( events[data_idx][ev], nr_of_bins,
                          linestyle='dashed', alpha=0.3,
                          label=events_labels[data_idx][ev] )

if plot_events:
    min_val = max(min([m - STD_DIST_FACTOR_EVENTS * std for m, std in event_stats]), 0)
    max_val = max([m + STD_DIST_FACTOR_EVENTS * std for m, std in event_stats])
    axes[1].set_xlim(min_val - 1, max_val + 1)

    axes[1].set_xlabel("# occurrence event")
    axes[1].legend()

prefix          = ""
title_instrs    = ", ".join(instrs_set)
xlabel_template = "# of cycles ({} bins)"
title_template = "Cycle latency of instruction{} {} (total: {})"

if title_addition:
    title_template += " (" + title_addition + ") "

# Set title for upper plot
fig.get_axes()[0].set_title(title_template.format(plural, title_instrs, runs))

logger.line(f"- Use number of bins: {nr_of_bins}")
ax.set_xlabel(xlabel_template.format( nr_of_bins ))
for curr_axis in fig.get_axes():
    curr_axis.set_ylabel("# of elements per bin")
ax.legend(loc=1)

if FILTER_OUTLIERS:
    footnote = "filtered {0:.3f}% outliers out".format(filtered_instr/total_instr)
    plt.text(0.75, 0.01, footnote, transform=plt.gcf().transFigure)

fig.tight_layout()

if (addition != ""):
    addition += "_"
    
plot_name = prefix + "_".join(sorted(instrs_set)) + "_" + \
            addition + str(runs) + "_plot"
 
plot_path = plot_folder + "/" + plot_name

## find unique name
inx=0
plot_path_un = plot_path
if isfile(plot_folder + "/.keep"):
    while isfile(plot_path_un + ".png"):
        inx += 1
        plot_path_un = plot_path + str(inx)

plot_path = plot_path_un + '.png'

plt.savefig(plot_path)

logger.line(f"- DONE, saved plot to file \"{plot_path}\"")
