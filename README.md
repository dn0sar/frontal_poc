# Frontal Attack PoC

## Setup

  - Please follow the installation instructions in the README_sgxstep.md to install SGXStep.
  
    To do that: run the two scripts: `install_SGX_driver.sh` and `install_SGX_SDK.sh`.
  Make sure to source the SGXSDK environment file after that.

  - The following boot kernel parameters must be specified:
    ```
    nox2apic iomem=relaxed no_timer_check isolcpus=1 nowatchdog nosmep nosmap
    ```

  - Make sure that the kernel module is loaded
    ```console
    make load -C kernel
    ```
  - Install python-3.6
    - Ubuntu 18.04 has the correct version in python3
    - Ubuntu 16.04 needs an [additional ppa to install python3.6 ](https://askubuntu.com/questions/865554/how-do-i-install-python-3-6-using-apt-get) 
  - Install the python requirements.txt in the app/frontal directory (pip3 install -r requirements.txt)
    ```
    cd app/frontal
    pip3 install -r requirements.txt
    ```

## Configuration

There are several parameters that can be tweaked in [app/frontal/Makefile.config](app/frontal/Makefile.config). The most important one is the `SGX_STEP_TIMER_INTERVAL` value that sets up the APIC counter for sgx-step. A suitable value will make sure that the script runs without errors. This value is platform specific.

Troubleshooting: 
  - Too high values will produce the followin error: 
    ```
    [main.c] ERROR: Detected 10000 abnormal runs.. Try to tweak the SGX_STEP_TIMER_INTERVAL value. (Currently it's probably too high)
    ```
  - Too low values will either produce a `segmentation fault` or will cause the program to wait indefinately. Try terminating and increasing the value if this happens

There are several other parameters that can be played with in [app/frontal/Makefile.config](app/frontal/Makefile.config). But the default ones should clearly show a high attack success probability.

**Important:** If you get a log with several of the following messages:
`[main.c] Caught fault 11! Restoring enclave page permissions.` Please make sure that `CR4.UMIP` bit is unset. This is necessary for the code to run properly.

## Running the Attack

Follow these few steps to run the PoC for the Frontal attack.

1. Go to the frontal poc: `cd app/frontal`
2. Make sure that the variable `ATTACK_SCENARIO` in [Makefile.config](Makefile.config) is set to `MICROBENCH` to run this PoC.
3. The command `make plot` runs the tests, plots the results and calculates the attack success probability
    - Plots are saved in the plot folder. Note that if the peaks for the two branches are not overlapping the CPU is vulnerable
    - Two attack success probabilities are then printed. For example:
        ```
        Hit rate half:   97.13%
        Hit best:        99.02%
        ```
        Any hit rate above 55% percent indicates that the CPU is clearly vulnerable.

The `MICROBENCH` scenario is set up with two blanaced branches that contain many `test` and `mov` instructions. The alignment of the branches can be changes with the `ALIGN1` and `ALIGN2` variables in [Makefile.config](Makefile.config). 

## Running the attack on a mock of the IPP library v2.9

As described in our paper, the Frontal attack can explpoit secret dependent branches that contain any write to memory. Even if these branches are perfectly identical, as long as the memory writes in them are aligned differently modulo 16 in the virtual address space.
This is the case in the IPP Library in several instances. We choose one particular example for this PoC: the `l9_ippsCmp_BN` function, which is used to compare two big numbers.
The function has 3 secret dependent paths, that are taken depending on whether the first number given to it is bigger, smaller, or equal to the second one.

The PoC creates a plot that shows the distribution of the single mov in each of these 3 paths. The plots show that the distribution of the same instruction (`mov %ecx, (%edx)`) present in the 3 paths. As long as these distribution do not overlap completely the attack succeds. Observe that we are measuring the same instruction and yet the plot show different distributions for them depending on the branch in which they are.

There are two ways to make the code not exploitable.
1. Remove secret dependent branches (expecially the ones that have a write to memory in them).
2. If a secret dependent branch with a write to memory in it must be present, the memory writes in them must be aligned the same way modulo 16 (see paper).

**Note1:** We run the library in our framework by copying the assembly code of the `l9_ippsCmp_BN` function rather than calling the library directly. The assmebly code we use contains the same instructions and is aligned the same way as the original IPP library. Since the binaries are essentially identical, if the attack is possible with our mock version, it is possible also with the full library. It just requires more effort to adapt our framework to and synchronize the attack with a full library.

**Note2:** As in SGX step our framework also allows to measure the number of instructions. We also report the detected number of instruction in our output. Each branch has a different number of instructions (196, 197, 198). This alone would also allow the attacker to exploit this function. But even if the number of instructions was the same, the frontal attack would still succeed.


Follow these few steps to run the PoC for the Frontal attack against a mock of the IPP library.

1. Go to the frontal poc: `cd app/frontal`
2. Make sure that the variable `ATTACK_SCENARIO` in [Makefile.config](Makefile.config) is set to `IPP_LIB` to run this PoC.
3. The command `make plot` runs the tests, plots the results
    - Plots are saved in the plot folder. Note that if the peaks for the two branches are not overlapping the CPU is vulnerable
    - The script prints the average time it took to execute each path. Whenever these averages differ significantly the attacker can distinguish between them.
        ```
        Detected 5000 iterations

        Detected 196 instructions in the bigger path    (1305 occurrences)
        Detected 198 instructions in the smaller path   (1262 occurrences)
        Detected 197 instructions in the equal path     (1173 occurrences)

        Avg execution time of bigger path (1305 occurrences):   8114.308045977012
        Avg execution time of smaller path (1262 occurrences):  8183.963549920761
        Avg execution time of equal path (1173 occurrences):    8187.452685421995

        !!!! The attacker can use the frontal attack to exploit this run of the code.
        --------------------------------------------------------------------------------
        Start plotting
        --------------------------------------------------------------------------------
        - Start parsing log file
              - Parsed log for instruction "mov     %ecx, (%rdx) (bigger)"
              - Parsed log for instruction "mov     %ecx, (%rdx) (smaller)"
              - Parsed log for instruction "mov     %ecx, (%rdx) (equal)"
        - Finished parsing log file
        - Filtered -206 outliers (from 3519 data points) out
        - Use number of bins: 390
        - DONE, saved plot to file "plots/mov_different_branches_1173_plot.png"
        ```

A plot is produced in the path given in the last line of the output of the command. As said above, the plot depicts the distributions of the `mov %ecx, (%edx)` in the three different secret dependent paths. If these distributions are not overlapping, the IPP library is exploitable. Note that the output of `make plot` also reports whether the version is exploitable.

We use a two different code snippets to mock the `l9_ippsCmp_BN` function. The first is [app/frontal/Enclave/asm_ipp_mock_sync.S](app/frontal/Enclave/asm_ipp_mock_sync.S). It contains the original library code with instructions after it to simulate various attack capabilities. This test case is run when `ATTACKER_SYNC` is set to `1` in  [Makefile.config](Makefile.config).
By setting the `ATTACKER_SYNC = 0` the [app/frontal/Enclave/asm_ipp_mock.S](app/frontal/Enclave/asm_ipp_mock.S) assembly file is used instead for the attack. This file contains a mock of the `l9_ippsCmp_BN` without any instructions after it. We describe the exact differences between these two test cases below.

### **Clarifications about the ATTACKER_SYNC parameter**
By running the exact copy of the new version of the IPP library (by setting `ATTACKER_SYNC = 0`), you will notice that the current version does not seem to be vulnerable to the frontal attack. Of course, it is still vulnerable because we can count the number of instructions and, by that, correctly estimate the path taken. Besides the number of instructions, in the equal path, the order of the instructions is also different from the other paths (the xor gets executed after the mov), so that branch can also be distinguished by observing the execution timing. However, if the branches would have the same number and type of instructions in them (and in the same order), the frontal attack cannot distinguish between the alignment of the `movs` currently used in the `l9_ippsCmp_BN` function. With `ATTACKER_SYNC = 1`, we want to highlight a small change that makes it vulnerable again. In the test run with `ATTACKER_SYNC=1`, we add several `movs` before the final return is performed. We do not change any of the branches themselves, only the instructions executed after them right before the return instruction.
We speculate that an attacker can leverage hyperthreading to inject these instructions in the frontend at the right time as well. With these additional `movs,` the branches are clearly distinguishable, despite the fact that the subsequent movs are not even interrupted (they are just present in the speculated instructions stream). We hypothesize that the same results could also be achieved by mispeculation. If the attacker can cause the CPU to speculate in a gadget that contains enough movs (independently of what they do), such an attacker can produce the same timing effects as seen when running with `ATTACKER_SYNC = 1`.

## Precomputed plots

There are a couple o examples of the outputs of the PoC in the [app/frontal/plots](app/frontal/plots) folder.
