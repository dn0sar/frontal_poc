# Information about the PoC settings

We reccomend to run the PoC using the appropriate Makefile targets, as they take care of correctly setting some environment variables and call the various scripts to parse and plot the results.

## Targets of the Makefile

The Makefile has the follwing targets. Their behaviour can be changed by setting the appropriate variables in the [Makefile.config](Makefile.config) file (See [Makefile.config Parameters describtion](#config_parameters) for more details)

- **all**: Compiles the sources.
- **run**: Comiles and runs the sources. The results of the run can be found in the [logs](logs) folder. In particular, three files are created after the run: `logs/out.txt`, `logs/measurements.txt`, and `logs/secrets.txt`. These files contain: a copy of the output also shown to screen during the run, a log of all the measurements, and a log of the secrets that were generated and used during the run, respectively.
- **parse**: First calls the run target and then parses the `logs/measurements.txt` files to extract only the timing of a specific instruction. In particular, during the **run** target execution the same victim binary gets executed multiple times, and the exeuction times of all the instructions are saved. The parse step extracts the timing of a specific instruction (i.e. removes all the other instructions' timings from each execution), so that later only a specific instruction can be plotted. The results are saved in the [logs](logs) folder.
- **plot**: Takes the results from the **parse** target and plots specific instructions. The plots are saved in the [plots](plots) folder. Note: after this target we also print in the command line the attack success probability.
- **plot-all**: This target only exists when ATTACK_SCENARIO=MICROBENCH (see below). Instead of plotting only one instruction it produces a plot for each instruction measured. The plots are saved in the [plots](plots) folder.

<a name="config_parameters"></a>

## Makefile.config Parameters describtion

There are three main kinds of parameters. Global, specific to the `MICROBENCH` attack scenario, and the ones specific to the `IPP_LIB` attack scenario.

### Global Parameters
The following parameters are schared from both attack scenarios.

- **SGX_STEP_TIMER_INTERVAL**: This is the timing that will be set as the APIC counter. See [SGX-Step](https://github.com/jovanbulck/sgx-step) for more details. Note that this can be left undefined if a `PLATFORM` is specified as in SGX-Step.
- **NUM**: Each ATTACK_SCENARIO contains a loop in which the same victim function is measured multiple times. This parameter sets how many times this loop is executed, and essentially increases the sample size.
- **ATTACK_SCENARIO**: There are two possible attack scenarios. `MICROBENCH` and `IPP_LIB`. They are descrbed in the main [README.md](../README.md) and we give a brief explanation of them and their attack specific parameters below.
- **PCM_ENABLED**: Can be either `0` or `1`. If enabled, alongside the timings, the performance counters are also recorded for each instruction. Details on how to specify the performance counters are given below.

### Parameters for PCM_ENABLED=1
The following parameters are only relevant if `PCM_ENABLED=1`, and are otherwise ignored.

Performance counters (PCM) to be measured can be added by adding strings describing them to the `EVENTS` variable. There is a limit on how many PCMs can be enabled at the same time, this is CPU specific. We listed all of the PCM supported and available in skylake in the [skylake_events](skylake_events). Simply copy the line with the PCM that you want to be measured there into the `Makefile.config` file and the results will be present in `logs/measurements.txt` and plotted when running the `plot` or `plot-all` target. As an example, to have two performance counters add the following lines in Makefile.config:

```
EVENTS += "UOPS_ISSUED.ANY-event=0xe,umask=0x1"
EVENTS += "L2_RQSTS.DEMAND_DATA_RD_MISS-event=0x24,umask=0x21"
```

### Parameters for ATTACK_SCNEARIO=MICROBENCH

The following parameters are only relevant if `ATTACK_SCNEARIO=MICROBENCH`, and are otherwise ignored.
In this attack scenario a victim function contaning two identical branches is created and measured.
A different branch is taken depending on the secret.
The goal of the attacker is to figure out which branch was taken, just by observing the execution timings of the victim function.
Different parameters configure how the branch looks like:

- **ALIGN1**: Sets the alignment modulo 16 of the `if` branch
- **ALIGN2**: Sets the alignment modulo 16 of the `else` branch
- **NUM_INSTR**: Sets the number of instructions contained in each branch. Note that the branches are identical. Each branch contains a sequence of `mov ; test ;` instuctions. When `NUM_INSTR=1` each branch contains a `mov`, `test`, and a `ret` instruciton.

The victim function can be found in [Enclave/asm_secret_branch.S](Enclave/asm_secret_branch.S). This file is generated after running `make all`.

### Parameters for ATTACK_SCNEARIO=IPP_LIB
The following parameters are only relevant if `ATTACK_SCNEARIO=IPP_LIB`, and are otherwise ignored.
This attack target attacks a mock of the `l9_ippsCmp_BN` function from the IPP library v2.9 as described in the main [README.md](../README.md).

- **INLINED_CALL**: can be either `0` or `1`. If set to `0` the binary used for the attack is [Enclave/asm_ipp_mock.S](Enclave/asm_ipp_mock.S), otherwise [Enclave/asm_ipp_mock_sync.S](Enclave/asm_ipp_mock_sync.S) is used.
