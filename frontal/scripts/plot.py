#!/usr/bin/python3

import re
# Next to lines are to use matplotlib without X server (display)
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import argparse
from colorama import Fore, Style
from scipy.stats import norm
from os.path import isfile

# Constant configuration variables
FILTER_OUTLIERS = True
STD_DEV_FACTOR  = 4

parser = argparse.ArgumentParser()
parser.add_argument("log_file", help="path to log file to parse")
parser.add_argument("-x_min", help="smallest x coordinate of plot", type=int)
parser.add_argument("-x_range", help="number of x coordinates (x_max = x_min"
                                     " + x_range)", 
                    type=int)
parser.add_argument("-p", "--plot_pattern", help="plot pattern (x-axis is measurement "
                                            "number, y-axis cycles) instead of normal "
                                            "histogram", 
                    action="store_true")
parser.add_argument("-b", "--plot_bars", help="plot bars for the mean measurement "
                                               "time of measured instructions number X "
                                               "module the given argument",
                     type=int)
parser.add_argument("-o", "--output_folder", help="path to folder for the produced "
                                                  "plots",
                        default="./plots")
parser.add_argument("-s", "--split_index", help="plots data by separating it in \"even and odd\" VA",
                        default=False, action="store_true")
parser.add_argument("-g", "--no_gaussian", help="fit a gaussian distribution on the plots",
                        default=True, action="store_false")
parser.add_argument("-n", "--num", help="only n points(from the beginning) will be used for plotting",
                        default=None, type=int)

args = parser.parse_args()

print("-"*80 + "\n\tStart plotting\n" + "-"*80)

data_file_path              = args.log_file
data_file_path_parts        = data_file_path.rsplit('/', 1)
data_file_name              = data_file_path_parts[-1]
measuring_outside_encl      = data_file_name.startswith("no_encl")
measuring_in_counter_mode   = data_file_name.startswith("counter")
measuring_only_zero_steps   = False
do_split                    = args.split_index
add_gaussian                = args.no_gaussian

plot_folder                 = args.output_folder

prep_log_file_path          = data_file_path_parts[0] + "/prep_" + \
                              data_file_path_parts[1] if len(data_file_path_parts) > 1 else ''
plot_prep_instr             = isfile(prep_log_file_path)
plot_pattern                = args.plot_pattern
nr_of_bars                  = args.plot_bars
plot_bars                   = nr_of_bars != None
plot_events                 = False
subsample_num               = args.num

if plot_pattern:
    print("- Plot pattern, therefore disable outlier filtering (would distort pattern)")
    FILTER_OUTLIERS = False
elif plot_bars:
    print("- Plot bars, therefore disable all filtering otherwise instruction counting"
             " gets shifted at filtered values")
    FILTER_OUTLIERS = False

if not plot_pattern and not plot_bars and args.x_min:
    # Set fixed x axis (that graphs can be compared)
    x_axis_min  = args.x_min
    x_range     = args.x_range
    x_axis_max  = x_axis_min + x_range
    nr_of_bins  = x_range // 2
    
    range_x_axis    = (x_axis_min, x_axis_max)
    xvals           = np.linspace(x_axis_min, x_axis_max, 20*x_range)
    deconv_xvals    = np.linspace(0, 500, 20 * 500)

# helper function
def error(msg):
    print(f"{Fore.RED}Error: {msg}{Style.RESET_ALL}")
    exit(1)

def warning(msg):
    print(f"{Fore.YELLOW}WARNING: {msg}{Style.RESET_ALL}")

def format_stats(mean, std):
    return (r' | $\mu \approx %.0f$' % (mean, )) \
            + (r', $\sigma \approx %.0f$' % (std, ))

def filter_list(mean, std, ls, factor = STD_DEV_FACTOR):
    return [elem for elem in ls
                    if abs(elem - mean) <= factor * std]

def bar_plot_set_ylim(ax, data):
    if data == []:
        warning("One instruction has no prepare instructions.")
        return

    y_max = max(data)
    y_min = min(data)

    space  = 50
    y_min -= space
    y_max += space

    ax.set_ylim(y_min, y_max)

def events_set_xlim(ax, stats, dist = 4):
    min_val = max(min([m - dist*std for m, std in stats]), 0)
    max_val = max([m + dist*std for m, std in stats])
    ax.set_xlim(min_val - 1, max_val + 1)

print("- Start parsing log file")
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

    if measuring_in_counter_mode:
        match           = re.search("Clocks per tick: ([0-9\.]+)", line)
        cycles_per_tick = float(match.groups()[0])
        line            = data_file.readline()
    elif measuring_outside_encl:
        match           = re.search("Overhead: ([0-9]+) cycles", line)
        overhead        = int(match.groups()[0])
        line            = data_file.readline()
        
    # Check if we first measured zero steps
    parsed_zero_steps   = False
    match   = re.search("Measuring ([0-9]+) zero steps", line)

    if (match != None):
        if plot_prep_instr:
            error("Cannot display zero steps and prepare instructions"
                  " at the same time");

        # Parse zero steps
        parsed_zero_steps   = True
        num_zero_steps      = int(match.groups()[0])

        zero_steps_data = [ ]
        for i in range(num_zero_steps):
            zero_steps_data.append( int(data_file.readline()) )

        print("\t- Parsed zero steps")
        line    = data_file.readline()

    if (line == ""):
        print("\t- Plot only zero steps")
        measuring_only_zero_steps   = True
        data                        = [ zero_steps_data ]
        runs                        = num_zero_steps
        instrs                      = ["zero_steps"]
        nr_of_parts                 = 1
        page_border_idx             = [[]]
    else:
        # Parse instructions
        if measuring_outside_encl:
            pattern     = "instruction (.+) \(runs: ([0-9]+)\)"   
        else:
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
                error("Wrong number of instructions!")


            groups          = match.groups()
            runs            = int(groups[2]) 
            plot_events     = plot_events or groups[1]
            instrs.append(groups[0])
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
                if do_split:
                    cycles = (cycles, i)

                # Apply page filters here if you want to inspect only
                # certain pages, for example:
                # 
                #if page_nr % 2 == 0:
                #if page_nr == 1 or page_nr == 197:

                data[nr_of_parts].append( cycles )
                [ events[nr_of_parts][ev].append(int(msr_str[ev + 1])) for ev in range(nr_events) ]
                if do_split:
                    for ev in range(nr_events):
                        events[nr_of_parts][ev][-1] = (events[nr_of_parts][ev][-1], i)
            
            if subsample_num:
                runs = subsample_num
                data[nr_of_parts] = data[nr_of_parts][:subsample_num]
                if nr_events > 0:
                    for i in range(len(events[nr_of_parts])):
                        events[nr_of_parts][i] = events[nr_of_parts][i][:subsample_num]

            print(f"\t- Parsed log for instruction \"{groups[0]}\"")


            if (do_split):
                part_name = instrs[-1]
                instrs[-1] = "Even indexes - " + part_name
                instrs.append("Odd indexes - " + part_name)
                runs = runs // 2
                curr_data = data[nr_of_parts][:]
                data[nr_of_parts] = [x for x,i in curr_data if i % 2 == 0]
                data.append([x for x,i in curr_data if i % 2 == 1])
                nr_of_parts += 1

                prev_names = events_names[-1]
                even_names = []
                odd_names  = []
                for i in range(nr_events):
                    part_name = prev_names[i]
                    even_names.append("Even - " + part_name)
                    odd_names.append("Odd - " + part_name)
                events_names[-1] = even_names
                events_names.append(odd_names)


                print(events_names)
                curr_data = events[nr_of_parts-1][:]
                events.append([])
                [events[nr_of_parts].append([]) for _ in range(nr_events)]
                for ev in range(nr_events):
                    events[nr_of_parts - 1][ev] = [x for x,i in curr_data[ev] if i % 2 == 0]
                    events[nr_of_parts][ev] = [x for x,i in curr_data[ev] if i % 2 == 1]
                
            
            nr_of_parts += 1;
            line         = data_file.readline()

print("- Finished parsing log file")

if plot_prep_instr:
    print("- Start parsing prepare instructions")
    with open(prep_log_file_path, "r") as prep_log_file:    
        prep_data = []

        line = prep_log_file.readline()
        while line != "":
            match       = re.search("Log ([0-9]+) prepare", line).groups()
            nr_of_prep  = int(match[0])

            prep_instrs = []
            for curr_prep_nr in range(nr_of_prep):
                line = prep_log_file.readline()
                if line != f"Prepare instruction number {curr_prep_nr}\n":
                    error("Prepare instructions log file format doesn't match")

                prep_instr_cycles = [0]*runs
                for i in range(runs):
                    prep_instr_cycles[i] = int( prep_log_file.readline() )

                prep_instrs.append(prep_instr_cycles)

            prep_data.append( prep_instrs )
            line = prep_log_file.readline()
        
    print("- Finished parsing prepare instructions")

if plot_bars and nr_of_parts > 1:
    warning("Bar plots with more than one instruction will be cluttered.") 

# Plot the data in even sized groups (using histograms)
do_convolution  = parsed_zero_steps and not measuring_only_zero_steps

# Deconvolve data to compensate the distribution created by enclave entries and exits
if do_convolution:
    print("- Approximate noise distribution")
    zero_norm_mean, zero_norm_std = norm.fit( zero_steps_data )

    zero_norm_fn  = norm.pdf(xvals, zero_norm_mean, zero_norm_std)

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

    if plot_prep_instr:
        prep_instr_filtered = []
        prep_stats[i]       = []

        for prep_instr in prep_data[i]:
            mean    = np.mean(prep_instr)
            std_dev = np.std(prep_instr)
            prep_stats[i].append( format_stats(mean, std_dev) )

            if FILTER_OUTLIERS:
                prep_instr_filtered.append( filter_list(mean, std_dev, prep_instr) )

        if FILTER_OUTLIERS:
            prep_data[i] = prep_instr_filtered

    if not plot_pattern and not plot_bars:
        if not args.x_min:
                # Set dynamic x coordinates if x_min was not given
                x_axis_min  = min(min(data)) - int(max(std_devs) * STD_DEV_FACTOR)
                x_axis_max  = max(max(data)) + int(max(std_devs) * STD_DEV_FACTOR)
                x_range     = x_axis_max - x_axis_min
                nr_of_bins  = x_range // 2
    
                range_x_axis    = (x_axis_min, x_axis_max)
                xvals           = np.linspace(x_axis_min, x_axis_max, 20*x_range)
                deconv_xvals    = np.linspace(0, 500, 20 * 500)

        # Throw error if data outside plot range
        #if range_x_axis[0] > min(data[i]) or range_x_axis[1] < max(data[i]):
        #    error(f"Some data (range ({min(data[i])}, {max(data[i])})) is outside "
        #          f"the plotted x range {range_x_axis}!")

if FILTER_OUTLIERS:
    total_instr     = runs * nr_of_parts
    filtered_instr  = total_instr - sum(len(x) for x in data)

    print("- Filtered {} outliers (from {} data points) out".format(
            filtered_instr, total_instr ))
else:
    print("- Filtering outliers is disabled")

## Make unique labels for legend
labels          = []
prep_labels     = []
events_labels   = []
instrs_set      = {instr.split(" ", 1)[0] for instr in instrs}
instrs_set_len  = len(instrs_set)

for i in range(nr_of_parts):
    instr_name = instrs[i]
    labels.append(instr_name.replace("$", "\\$") + (format_stats(means[i], std_devs[i]) if add_gaussian else ''))

    if plot_prep_instr:
        prep_labels_for_instr = []
        for prep_nr in range(len(prep_data[i])): 
            prep_labels_for_instr.append(f"prep {prep_nr}" + prep_stats[i][prep_nr])

        prep_labels.append(prep_labels_for_instr)

    if plot_events: 
        part_labels = []
        for ev_nr in range(len(events[i])):
            # TODO: Parse from the file the event name
            part_labels.append(f"{events_names[i][ev_nr]} instr {i}") 
        events_labels.append(part_labels)

plural = ""
if (instrs_set_len > 1):
    plural = "s"

# Plot data with fitted normal distribution and
# if error was measured also deconvolution.

if do_convolution:
    fig, axes   = plt.subplots(nrows = 2, figsize=(9,5), dpi=200)
    ax          = axes[0]
elif plot_prep_instr:
    fig, axes   = plt.subplots(nrows = 2, figsize=(9,5), dpi=200)
    ax          = axes[1]
elif plot_events:
    fig, axes   = plt.subplots(nrows = 2, figsize=(14,10), dpi=200)
    ax          = axes[0]
else:
    fig, ax     = plt.subplots(figsize=(9,5), dpi=200)

# Plot data
default_colors  = plt.rcParams['axes.prop_cycle'].by_key()['color']
bar_all_means   = []

for data_idx in range(nr_of_parts):
    d            = data[data_idx]

    if plot_pattern:
        ax.plot(d, ".-", label=labels[data_idx], markersize=3, 
                linewidth=.25, color=default_colors[data_idx])
    elif plot_bars:
        print("- Start plotting bars")
        
        group_width = 0.9
        y_max       = np.mean(d)
        y_min       = y_max

        bar_pos         = []
        bar_widths      = []
        bar_means       = []
        bar_stds        = []

        if plot_prep_instr:
            prep_nr         = len(prep_data[data_idx])
            bar_prep_pos    = [ [] for i in range(prep_nr) ]
            bar_prep_widths = [ [] for i in range(prep_nr) ]
            bar_prep_means  = [ [] for i in range(prep_nr) ]
            bar_prep_std    = [ [] for i in range(prep_nr) ]

        for n_th_entries in range(1, nr_of_bars+1):
            bar_width       = group_width / n_th_entries

            # Start at "start_idx" entry and take every n-th entry into list
            for start_idx in range(n_th_entries):
                nth_data        = d[start_idx :: n_th_entries]

                # Remove page border outliers
                for page_border_i in page_border_idx[data_idx]:
                    if (page_border_i - start_idx) % n_th_entries == 0:
                        nth_data.remove( d[page_border_i] )

                # Position n bars around n-th entry
                bar_pos.append( n_th_entries + (start_idx * bar_width - group_width/2)
                                + bar_width / 2 )
                bar_widths.append(bar_width)
                bar_means.append( np.mean( nth_data ) )
                bar_stds.append( np.std( nth_data) )

                if plot_prep_instr:
                    for prep_idx in range( len(prep_data[data_idx]) ):
                        prep_d = prep_data[data_idx][prep_idx]
                        nth_prep_data   = prep_d[start_idx :: n_th_entries]
                        
                        bar_prep_pos[prep_idx].append( bar_pos[-1] )
                        bar_prep_widths[prep_idx].append(bar_width)
                        bar_prep_means[prep_idx].append( np.mean(nth_prep_data) )
                        bar_prep_std[prep_idx].append( np.std(nth_prep_data) )

        bar_all_means += bar_means

        # With more than 8 entries, this just clutters the plot
        if nr_of_bars > 8:
            bar_stds = None

        ax.bar(bar_pos, bar_means, bar_widths, yerr=bar_stds, alpha=0.3,
                       label=labels[data_idx], color=default_colors[data_idx],
                       error_kw=dict(elinewidth=0.5, capsize=5, capthick=0.5))

        if plot_prep_instr:
            all_means = [mean for means in bar_prep_means for mean in means]
            bar_plot_set_ylim(axes[0], all_means)

            if nr_of_bars > 8:
                bar_prep_std[prep_idx] = None

            for prep_idx in range( len(prep_data[data_idx]) ):
                axes[0].bar(bar_prep_pos[prep_idx], bar_prep_means[prep_idx], 
                            bar_prep_widths[prep_idx], yerr=bar_prep_std[prep_idx], 
                            alpha=0.3, label=prep_labels[data_idx][prep_idx],
                            color=default_colors[data_idx], 
                            error_kw=dict(elinewidth=0.5, capsize=5, capthick=0.5))
    else:
        bins_y, _, _ = ax.hist(d, nr_of_bins, 
                                range=range_x_axis, histtype='stepfilled', 
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

        if do_convolution:
            # Plot deconvolution
            # The deconvolution of two normal distributions N1(m1,s1), N2(m2,s2) is
            # N3(m1 + m2, sqrt(s1^2 + s2^2))
            conv_mean   = norm_mean - zero_norm_mean
            conv_std    = np.sqrt( norm_std**2 - zero_norm_std**2 )
            conv_norm   = norm.pdf(deconv_xvals, conv_mean, conv_std)
            
            conv_label  = instrs[data_idx].replace("$", "\\$") + " recovered"\
                            + format_stats(conv_mean, conv_std)

            axes[1].plot(deconv_xvals, conv_norm, label=conv_label, 
                         linewidth=1.0, color=default_colors[data_idx])
        elif plot_prep_instr:
            # Hacky title (invisible, empty histogram)
            instr_escaped = instrs[data_idx].replace("%", "\\%").replace(" ", "\\ ")\
                            .replace("$", "\$")
            subtitle = rf'$\bf{{{instr_escaped}}}$'
            axes[0].hist( [], nr_of_bins,
                          alpha=0, linestyle='None',
                          range=range_x_axis, histtype='step',
                          label=subtitle )

            # Plot prepare instructions explicitly because otherwise matplotlib 
            # plots them in reverse order
            for prep_nr in range( len(prep_data[data_idx]) ):
                axes[0].hist( prep_data[data_idx][prep_nr], nr_of_bins, 
                              range=range_x_axis, histtype='step',
                              label=prep_labels[data_idx][prep_nr] )
        elif plot_events:
            for ev in range (len(events[data_idx])):
                axes[1].hist( events[data_idx][ev], nr_of_bins,
                              linestyle='dashed', alpha=0.3,
                              label=events_labels[data_idx][ev] )


if plot_events:
    events_set_xlim(axes[1], event_stats) 
    axes[1].set_xlabel("# occurrence event")
    axes[1].legend()

if plot_bars:
    bar_plot_set_ylim(ax, bar_all_means)
    ax.set_xticks( np.arange(1, nr_of_bars+1) )

if do_convolution:
    print("- Deconvolved fitted data with fitted error distribution")

    axes[1].legend()

    # Plot error
    error_label  = "noise (ERESUME + AEX)" + format_stats(zero_norm_mean, zero_norm_std)
    bins_y, _, _ = ax.hist(zero_steps_data, nr_of_bins, color='r', 
                            range=range_x_axis, histtype='stepfilled', 
                            label=error_label, alpha=0.3)

    zero_norm_fn_scaled = zero_norm_fn * np.max(bins_y) / np.max( zero_norm_fn )
    ax.plot(xvals, zero_norm_fn_scaled, color='r', linewidth=.75, linestyle='dashed')
elif plot_prep_instr:
    axes[0].legend(loc=1)

prefix          = ""
title_instrs    = ", ".join(instrs_set)
xlabel_template = "# of cycles ({} bins)"
if measuring_outside_encl:
    prefix = "no_encl_"
    title_template = "Cycle latency of instruction{} {} outside enclave (total: {}, " \
                     f"overhead: {overhead} cycles)"
elif measuring_in_counter_mode:
    title_template  = "Latency of instruction{} {} (total: {})"
    xlabel_template = r"# of counter ticks, 1 tick $\approx$ %.1f cycles" \
                        % cycles_per_tick + " ({} bins)"
elif plot_pattern:
    title_template  = "Cycles of instruction{} {} for " + ( "first " if subsample_num else "" ) + "{} measurements"
    prefix = "pattern_"
elif plot_bars:
    title_template  = "Mean of cycles for n-th measurement of instruction{} {}" \
                      " (total: {})"
    prefix = f"bars_{nr_of_bars}_"
else:
    title_template = "Cycle latency of instruction{} {} (total: {})"

if plot_prep_instr:
    prefix = "with_prep_" + prefix

title_template += " (" + title_addition + ") " if title_addition else ''

# Set title for upper plot
fig.get_axes()[0].set_title(title_template.format(plural, title_instrs, runs))

if plot_pattern:
    ax.set_xlabel("Measurement")
    for curr_axis in fig.get_axes():
        curr_axis.set_ylabel("Cycles")
elif plot_bars:
    ax.set_xlabel("Every n-th measurement (starting with index 0, 1, ..., n-1)")
    for curr_axis in fig.get_axes():
        curr_axis.set_ylabel("Mean #cycles")
else:
    print(f"- Use number of bins: {nr_of_bins}")
    ax.set_xlabel(xlabel_template.format( nr_of_bins ))
    for curr_axis in fig.get_axes():
        curr_axis.set_ylabel("# of elements per bin")
ax.legend(loc=1)

if parsed_zero_steps and not measuring_only_zero_steps:
    if prefix != "":
        prefix += "_"
    
    prefix += "with_zero_steps_"

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

print(f"- DONE, saved plot to file \"{plot_path}\"")
