MAKEFILE_DIR        = $(realpath $(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
PLOTS_DIR           = $(MAKEFILE_DIR)/plots
LOGS_DIR            = $(MAKEFILE_DIR)/logs
SCRIPTS_DIR         = $(MAKEFILE_DIR)/scripts

PARSE_SCRIPT        = $(SCRIPTS_DIR)/parse.py
PARSE_IPP_SCRIPT    = $(SCRIPTS_DIR)/parse_ipp.py
PLOT_SCRIPT         = $(SCRIPTS_DIR)/plot.py
ATTACK_SUCC_SCRIPT  = $(SCRIPTS_DIR)/attack_success.py


PROJECT_TOP          = ..
LIBSGXSTEP_DIR       = $(PROJECT_TOP)/sgx-step
LIBSGXSTEP           = $(LIBSGXSTEP_DIR)/libsgxstep
-include $(LIBSGXSTEP)/Makefile.config

ifeq ($(SGX_SDK),)
    SGX_SDK          = /opt/intel/sgxsdk
endif
export SGX_SDK
ifndef URTS_LD_LIBRARY_PATH 
    ifneq ($(SGX_SDK), /opt/intel/sgxsdk)
        URTS_LD_LIBRARY_PATH = LD_LIBRARY_PATH=$(LIBSGXSTEP_DIR)/linux-sgx/psw/urts/linux
    endif
endif

ENCLAVE              = Enclave
PCU_DIR				 = $(PROJECT_TOP)/pcm
SUBDIRS              = $(ENCLAVE) $(LIBSGXSTEP)

CC                   = gcc
AS                   = gcc
LD                   = gcc

ifeq ($(M32), 1)
	ASFLAGS  = -m32 -DM32=$(M32)
	CFLAGS   = -m32 -DM32=$(M32)
	LDFLAGS  = -m32
else
	LIB_SUFX = 64
endif

include Makefile.config
export ATTACKER_SYNC

CFLAGS              += -fPIC -fno-stack-protector -fno-builtin -fno-jump-tables \
                       -fno-common -Wno-attributes -g -D_GNU_SOURCE -O0
INCLUDE              = -I$(PROJECT_TOP) -I$(SGX_SDK)/include/ -I$(LIBSGXSTEP_DIR)
LDFLAGS             += -lsgx-step -lencl_proxy -lsgx_urts \
                       -lsgx_uae_service -pthread $(SUBDIRS:%=-L %) -L$(SGX_SDK)/lib$(LIB_SUFX)/ \
                       -L$(LIBSGXSTEP_DIR)/linux-sgx/psw/urts/linux

SOURCES              = $(shell ls *.c)
PCM_SOURCES          = $(PCU_DIR)/msr.cpp $(PCU_DIR)/cpucounters.cpp $(PCU_DIR)/pci.cpp $(PCU_DIR)/mmio.cpp $(PCU_DIR)/client_bw.cpp $(PCU_DIR)/utils.cpp $(PCU_DIR)/perf_counters.cpp
PCM_OBJ              = $(PCU_DIR)/mylibPCM.a
OBJECTS              = $(SOURCES:.c=.o)
OUTPUT               = app

# Used to enable the collection and plotting of performance counters
ifeq ($(PCM_ENABLED), 1)
        LIBSUBDIRS              += $(PCU_DIR)
        OBJECTS         		+= $(PCM_OBJ)
        LD            		    = g++
        SGX_MODE          		= SGX_PRERELEASE
        PCM_SILENT				= 1
        export PCM_SILENT
    ifdef EVENTS
        NUM_PCMS=$(words $(EVENTS))
    endif
else
        PCM_ENABLED       = 0
        PCM_INSTR_ENABLED = 0
endif

BUILDDIRS						= $(SUBDIRS:%=build-%)
LIBBUILDDIRS                    = $(LIBSUBDIRS:%=build-%)
CLEANDIRS						= $(SUBDIRS:%=clean-%)
LIBCLEANDIRS                    = $(LIBSUBDIRS:%=clean-%)
LOGS							= $(wildcard $(LOGS_DIR)/*.log) $(LOGS_DIR)/out.txt $(LOGS_DIR)/secrets.txt $(LOGS_DIR)/measurements.txt $(LOGS_DIR)/ipp_meas.txt

ifndef NUM
    NUM             = 100
endif

ifndef NUM_INSTR
    NUM_INSTR       = 25
endif

export NUM
export NUM_INSTR
export ALIGN1
export ALIGN2
export SGX_STEP_TIMER_INTERVAL

CFLAGS += -DATTACK_SCENARIO=$(ATTACK_SCENARIO) -DNUM_RUNS=$(NUM) -DPCM_ENABLED=$(PCM_ENABLED) -DNUM_PCMS=${NUM_PCMS}

ifdef SGX_STEP_TIMER_INTERVAL
	CFLAGS += -DSGX_STEP_TIMER_INTERVAL=${SGX_STEP_TIMER_INTERVAL}
endif

.SILENT:
.ONESHELL: run


all: $(OUTPUT)
	
run: clean all
	touch $(LOGS_DIR)/out.txt
	tail -f $(LOGS_DIR)/out.txt & TAIL_PID=$$!
	$(URTS_LD_LIBRARY_PATH) ./app $(EVENTS) > $(LOGS_DIR)/out.txt || EXIT_CODE=$$?
	kill -TERM $$TAIL_PID
	exit $$EXIT_CODE

ifeq ($(ATTACK_SCENARIO),IPP_LIB)
parse: run
	$(PARSE_IPP_SCRIPT) $(LOGS_DIR)/measurements.txt > $(LOGS_DIR)/ipp_meas.txt

plot: parse
	$(PLOT_SCRIPT) -o $(PLOTS_DIR) $(LOGS_DIR)/ipp_meas.txt
else
parse: run
	$(PARSE_SCRIPT) -r ${NUM} -i ${NUM_INSTR}

plot: parse
	$(PLOT_SCRIPT) -o $(PLOTS_DIR) $(LOGS_DIR)/movs_0_${NUM}.log
	# The following will compute the success probability based on the first mov
	$(ATTACK_SUCC_SCRIPT) -j 1 -s $$(( 2 * $(NUM_INSTR) + 1 )) -i 2 $(LOGS_DIR)/measurements.txt $(LOGS_DIR)/secrets.txt 

plot-all: SHELL:=/bin/bash
plot-all: parse
	for i in {1..${NUM_INSTR}}; do $(PLOT_SCRIPT) -o $(PLOTS_DIR) $(LOGS_DIR)/movs_$$((i-1))_${NUM}.log; done
endif

$(OUTPUT): $(BUILDDIRS) $(LIBBUILDDIRS) $(OBJECTS)
	echo "$(INDENT)[LD]" $(OBJECTS) $(LIBS) -o $(OUTPUT) 
	$(LD) $(OBJECTS) $(LDFLAGS) -o $(OUTPUT) 

%.o : %.c
	echo "$(INDENT)[CC] " $<
	$(CC) $(CFLAGS) $(INCLUDE) -c $<

%.o : %.S
	echo "$(INDENT)[AS] " $<
	$(AS) $(ASFLAGS) $(INCLUDE) -c $< -o $@

clean: $(CLEANDIRS)
	echo "$(INDENT)[RM]" $(OBJECTS) $(OUTPUT)
	rm -f $(OBJECTS) $(OUTPUT)
	rm -f $(LOGS)

$(BUILDDIRS):
	echo "$(INDENT)[===] $(@:build-%=%) [===]"
	$(MAKE) -C $(@:build-%=%) INDENT+="$(INDENT_STEP)" M32=$(M32) curr-dir=$(curr-dir)/$(@:build-%=%)

$(LIBBUILDDIRS):
	echo "$(INDENT)[===] $(@:build-%=%) [===]"
	$(MAKE) lib -C $(@:build-%=%) INDENT+="$(INDENT_STEP)" curr-dir=$(curr-dir)/$(@:build-%=%)

$(CLEANDIRS):
	echo "$(INDENT)[===] $(@:clean-%=%) [===]"
	$(MAKE) clean -C $(@:clean-%=%) INDENT+="$(INDENT_STEP)" curr-dir=$(curr-dir)/$(@:build-%=%)

$(LIBCLEANDIRS):
	echo "$(INDENT)[===] $(@:clean-%=%) [===]"
	$(MAKE) clean -C $(@:clean-%=%) INDENT+="$(INDENT_STEP)" curr-dir=$(curr-dir)/$(@:build-%=%)
