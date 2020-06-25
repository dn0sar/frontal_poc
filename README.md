# Frontal Attack PoC

## Abstract

We introduce a new timing side-channel attack on Intel CPU processors. Our Frontal attack exploits the way that CPU frontend fetches and processes instructions while being interrupted. In particular, we observe that in modern Intel CPUs, some instruction's execution times will depend on which operations precede and succeed them, and on their virtual addresses. Unlike previous attacks that could only profile branches if they contained different code or were based on conditional jumps, the attack allows the adversary to distinguish between instruction-wise identical branches. As the attack requires OS capabilities to set the interrupts, we use it to exploit SGX enclaves. Our attack demonstrates that a realistic SGX attacker can always observe the full enclave instruction trace, and secret-depending branching should not be used even alongside defenses to current controlled-channel attacks. We show that the adversary can use the Frontal attack to extract a secret from an SGX enclave if that secret was used as a branching condition for two instruction-wise identical branches. The attack can be exploited against several crypto libraries and affects all Intel CPUs.

```
@misc{puddu2020frontal,
    title={Frontal Attack: Leaking Control-Flow in SGX via the CPU Frontend},
    author={Ivan Puddu and Moritz Schneider and Miro Haller and Srdjan Čapkun},
    year={2020},
    eprint={2005.11516},
    archivePrefix={arXiv},
    primaryClass={cs.CR}
}
```

The paper and the attack are based upon initial observations made during Miro Haller's [Bachelor thesis](https://github.com/Miro-H/bachelor-thesis-sgx).

## Setup

  - Please follow the installation instructions in the [sgx-step/README.md](sgx-step/README.md) to install SGXStep.
  
    To do that: run the two scripts: `install_SGX_driver.sh` and `install_SGX_SDK.sh`.
  Make sure to source the SGXSDK environment file after that.

  - The following boot kernel parameters must be specified:
    ```
    nox2apic iomem=relaxed no_timer_check isolcpus=1 nowatchdog nosmep nosmap
    ```

  - Make sure that the kernel module is loaded
    ```
    make load -C sgx-step/kernel
    ```
  - Install python-3.6
    - Ubuntu 18.04 has the correct version in python3
    - Ubuntu 16.04 needs an [additional ppa to install python3.6 ](https://askubuntu.com/questions/865554/how-do-i-install-python-3-6-using-apt-get) 
  - Install the python requirements.txt in the [frontal](frontal) directory
    ```
    pip3 install -r frontal/requirements.txt
    ```

## Configuration

There are several parameters that can be tweaked in [frontal/Makefile.config](app/frontal/Makefile.config). The most important one is the `SGX_STEP_TIMER_INTERVAL` value that sets up the APIC counter for sgx-step. A suitable value will make sure that the script runs without errors. This value is platform specific see also [sgx-step/README.md](sgx-step/README.md). Note that for the frontal attack we use the a APIC division of 1. Hence, as a rule of thumb the values for the stock SGX-Step need to be roughly doubled to work with our changes.

Troubleshooting: 
  - Too high values will produce an error similar to the following: 
    ```
    [main.c] ERROR: Detected 10000 abnormal runs.. Try to tweak the SGX_STEP_TIMER_INTERVAL value. (Currently it's probably too high)
    ```
  - Too low values will either produce a `segmentation fault` or will cause the program to wait indefinately. Try first to re-load the kernel module and relaunching the app in these cases, and if the errors keep happening increase the value of `SGX_STEP_TIMER_INTERVAL`.

There are several other parameters that can be played with in [app/frontal/Makefile.config](app/frontal/Makefile.config). But the default ones should clearly show a high attack success probability.

**Important:** If you get a log with several of the following messages:
`[main.c] Caught fault 11! Restoring enclave page permissions.` Please make sure that CPU `CR4.UMIP` bit is unset. This is necessary for the code to run properly.

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

As described in our paper, the Frontal attack can exploit secret dependent branches that contain any write to memory. Even if these branches are perfectly identical, as long as the memory writes in them are aligned differently, modulo 16 in the virtual address space.
This is the case in the IPP Library in several instances. We choose one particular example for this PoC: the `l9_ippsCmp_BN` function, which is used to compare two big numbers.
The function has three secret dependent paths that are taken depending on whether the first number given to it is bigger, smaller, or equal to the second one.

The PoC creates a plot that shows the distribution of the single mov in each of these three paths. The plots show that the distribution of the same instruction (`mov %ecx, (%edx)`) present in the three paths. As long as these distributions do not overlap completely, the attack succeeds. Observe that we measure the same instruction, and yet the plot show different distributions for them depending on the branch in which they are.

There are two ways to make the code not exploitable.
1. Remove secret dependent branches (especially the ones that have a write to memory in them).
2. If a secret dependent branch with a write to memory must be present, the memory writes in them must be aligned the same way modulo 16 (see paper).

**Note1:** We run the library in our framework by copying the assembly code of the `l9_ippsCmp_BN` function rather than calling the library directly. The assembly code we use contains the same instructions and is aligned the same way as the original IPP library. Since the binaries are virtually identical, if the attack is possible with our mock version, it is possible also with the full library. It just requires more effort to adapt our framework to and synchronize the attack with a full library.

**Note2:** As in SGX-Step, our framework also allows us to measure the number of instructions. We also report the detected number of instructions in our output. Each branch has a different number of instructions (196, 197, 198). This alone would also allow the attacker to exploit this function. But even if the number of instructions were the same, the frontal attack would still succeed.


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
By running the exact copy of the new version of the IPP library (by setting `ATTACKER_SYNC = 0`), you will notice that the current version does not seem vulnerable to the frontal attack. Of course, the function itself is still vulnerable because we can count the number of instructions and, by that, correctly estimate the path taken. Besides the instruction number, the order of the instructions in the equal path is also different compared to the other paths (the xor gets executed after the mov). Hence, the equal path can also be distinguished by observing the execution timing of a particular (unknown) instruction. However, if the branches would have the same number and type of instructions in them (and in the same order), the frontal attack cannot distinguish between the alignment of the `movs` currently used in the `l9_ippsCmp_BN` function. With `ATTACKER_SYNC = 1`, we want to highlight a small change that makes it vulnerable again, by keeping the same alignment. In the test run with `ATTACKER_SYNC=1`, we add several `movs` before the final return is performed. We do not change any of the branches themselves, only the instructions executed after them right before the return instruction.
With these additional `movs,` the branches are clearly distinguishable, despite the fact that the subsequent movs are not even interrupted (they are just present in the speculated instructions stream).
We think that there are two scenarios in which this type of attack could be realistic.
First, an attacker can leverage hyperthreading to inject these instructions in the front end at the right time, although this is technically challenging. Second, we also hypothesize that this could be observed if the CPU mis-speculates to a path with a couple of consecutive movs. We did not yet test these two scenarios to see if they produce the same effects as `ATTACKER_SYNC=1`.

## Precomputed plots

There are a couple o examples of the outputs of the Frontal attack PoC in the [app/frontal/plots](app/frontal/plots) folder.
