## SGX settings ##

# Setting SGX_MODE to SGX_PRODUCTION throws an exception since to build production 
# enclaves an intel developer license is needed: A token that is given as
# an argument to create_sgx_enclave(), which is located at /root/enclave.token.
# See linux-sgx/SampleCode for applications that read this token correctly

SGX_DEBUG		= 0
SGX_PRODUCTION	= 1
SGX_PRERELEASE	= 2
SGX_OPTIMIZE	?= 1

SGX_MODE ?= SGX_PRERELEASE
export SGX_MODE
export SGX_OPTIMIZE

PROJECT_TOP					= ../../../..
LIBSGXSTEP_DIR			= $(PROJECT_TOP)
LIBSGXSTEP					 = $(LIBSGXSTEP_DIR)/libsgxstep
-include $(LIBSGXSTEP)/Makefile.config

ifeq ($(SGX_SDK),)
		SGX_SDK					 = /opt/intel/sgxsdk
endif
export SGX_SDK
ifneq ($(SGX_SDK), /opt/intel/sgxsdk)
		URTS_LD_LIBRARY_PATH = LD_LIBRARY_PATH=$(LIBSGXSTEP_DIR)/linux-sgx/psw/urts/linux
endif

ENCLAVE							= ../Enclave
COMMON_DIR						= ../..
COMMON							= $(COMMON_DIR)/Common
PCU_DIR							= $(PROJECT_TOP)/pcm
SUBDIRS							= $(ENCLAVE) $(LIBSGXSTEP) $(COMMON)

CC								= gcc-4.8
AS								= gcc-4.8
LD								= gcc-4.8

CFLAGS							+= -fPIC -fno-stack-protector -fno-builtin -fno-jump-tables \
											 -fno-common -Wno-attributes -D_GNU_SOURCE
INCLUDE							= -I$(SGX_SDK)/include/ -I$(LIBSGXSTEP_DIR) -I$(COMMON_DIR) -I..
LDFLAGS							+= -lsgx-step -lencl_proxy -lsgx_urts \
											 -lsgx_uae_service -pthread $(SUBDIRS:%=-L %) -L$(SGX_SDK)/lib64/ \
											 -L$(LIBSGXSTEP_DIR)/linux-sgx/psw/urts/linux

PCMLDFLAGS						= -pthread -lrt

SOURCES							= $(wildcard *.c)
COMMON_SOURCES	        		= $(wildcard $(COMMON)/*.c)
PCM_SOURCES                     = $(PCU_DIR)/msr.cpp $(PCU_DIR)/cpucounters.cpp $(PCU_DIR)/pci.cpp $(PCU_DIR)/mmio.cpp $(PCU_DIR)/client_bw.cpp $(PCU_DIR)/utils.cpp $(PCU_DIR)/perf_counters.cpp
OBJECTS							= $(SOURCES:.c=.o) $(COMMON_SOURCES:.c=.o)
OUTPUT							= app

EXTRA_OBJECTS = $(PCU_DIR)/mylibPCM.a
LD            = g++
PCM_ENABLED   = 1

ifeq ($(SGX_OPTIMIZE), 1)
		CFLAGS	+= -O2
		LDFLAGS += -O2
else
		CFLAGS	+= -g -O0
endif

ifeq ($(SGX_MODE), $(SGX_PRODUCTION))
		CFLAGS += -DNDEBUG -UEDEBUG -UDEBUG
else ifeq ($(SGX_MODE), $(SGX_PRERELEASE))
		CFLAGS += -DNDEBUG -DEDEBUG -UDEBUG
endif

LOG_FOLDER	= logs
LOG_FILE		= $(LOG_FOLDER)/microbenchmark_cycles.log
SECRET_IN		= $(LOG_FOLDER)/secret_input.txt



## Compile parameters ##
# default output folder for plots
ifeq ($(PLOTS_FOLDER),)
		PLOTS_FOLDER = ./plots
endif

# Also log prepare instructions into separate log file and plot them too
ifeq ($(LOG_PREP_INSTRS),)
		LOG_PREP_INSTRS = 0
endif

# Log zero steps, plot them and do deconvolution with instruction measurements
ifeq ($(LOG_ZERO_STEPS),)
		LOG_ZERO_STEPS	= 0
endif

# Number of measured zero steps
ifeq ($(ZERO_STEPS_NUM),)
		ZERO_STEPS_NUM = 100000
endif
export LOG_ZERO_STEPS

# Number of measured instructions
ifeq ($(NUM),)
		NUM = 100000
endif

# To only log zero steps, we just add zero instructions to the enclave
ifeq ($(ONLY_ZERO_STEPS), 1)
		NUM = 0
endif

# Set to run "poor man's cmov" PoC
ifeq ($(POOR_MANS_CMOV),)
		POOR_MANS_CMOV			= 0
else
		NUM_POOR_MANS_CMOV	= 11
		#NUM_POOR_MANS_CMOV  = 53
		NUM								 := $(shell expr $(NUM) \* $(NUM_POOR_MANS_CMOV))
endif

export NUM

# Measured instruction
ifeq ($(TESTED_INSTR),)
		TESTED_INSTR		= NOP
endif
export TESTED_INSTR

# Plot pattern (x-axis is measurement number, y-axis cycles) instead of normal histogram
ifeq ($(PLOT_PATTERN),)
		PLOT_PATTERN = 0
endif

ifeq ($(PLOT_PATTERN),1) 
		ifeq ($(LOG_PREP_INSTRS),1)
				$(error PLOT_PATTERN cannot be used together with LOG_PREP_INSTRS)
		endif
		
		ifeq ($(LOG_ZERO_STEPS),1)
				$(error PLOT_PATTERN cannot be used together with LOG_ZERO_STEPS)
		endif
endif

# Plot bars by grouping measurements (modulo PLOT_BARS) together
ifeq ($(PLOT_BARS),)
		PLOT_BARS = 0
endif

ifneq ($(PLOT_BARS),0)
		ifeq ($(LOG_ZERO_STEPS),1)
				ifneq ($(ONLY_ZERO_STEPS), 1)
						$(error PLOT_BARS can only be used together with LOG_ZERO_STEPS if no \
										other instruction is plotted, i.e. ONLY_ZERO_STEPS is used )
				endif
		endif
endif

BUILDDIRS						= $(SUBDIRS:%=build-%)
CLEANDIRS						= $(SUBDIRS:%=clean-%)
LOGS							= $(wildcard logs/*.log) logs/out.txt logs/secret

CFLAGS += -DNUM_RUNS=$(NUM) -DTESTED_INSTR=$(TESTED_INSTR) \
					-DLOG_ZERO_STEPS=$(LOG_ZERO_STEPS) -DZERO_STEPS_NUM=$(ZERO_STEPS_NUM) \
					-DSGX_MODE=$(SGX_MODE) -DLOG_PREP_INSTRS=${LOG_PREP_INSTRS} \
					-DPOOR_MANS_CMOV=${POOR_MANS_CMOV} -DNUM_POOR_MANS_CMOV=${NUM_POOR_MANS_CMOV} \
                    -DPCM_ENABLED=$(PCM_ENABLED)

## Make targets ##
.SILENT:
all: $(OUTPUT)
	
rebuild: clean all

run: clean all
	sudo $(URTS_LD_LIBRARY_PATH) ./app > logs/out.txt
	cat logs/out.txt

run-no-clean: all
	sudo $(URTS_LD_LIBRARY_PATH) ./app > logs/out.txt
	cat logs/out.txt

run-mult: clean all
	tmux new -d '../Scripts/run-app-mult-times.sh $(ZERO_STEPS_NUM)'

rerun: 
	./app > logs/out.txt
	cat logs/out.txt

ifneq ($(PLOT_BARS), 0)
plot: run
	[ $$? -eq 0 ] && $(COMMON)/plot.py -o $(PLOTS_FOLDER) -b $(PLOT_BARS) \
	$(LOG_FILE)
else ifeq ($(LOG_ZERO_STEPS),1)
plot: run
	[ $$? -eq 0 ] && $(COMMON)/plot.py -o $(PLOTS_FOLDER) \
	-x_min $(ZERO_STEPS_PLOT_X_MIN) \
	-x_range $(ZERO_STEPS_PLOT_RANGE_X) $(LOG_FILE)
else ifeq ($(PLOT_PATTERN),1)
plot: run
	[ $$? -eq 0 ] && $(COMMON)/plot.py -o $(PLOTS_FOLDER) -p $(LOG_FILE)
else
plot: run
	[ $$? -eq 0 ] && $(COMMON)/plot.py -o $(PLOTS_FOLDER) \
	-x_min $(DEFAULT_PLOT_X_MIN) \
	-x_range $(DEFAULT_PLOT_RANGE_X) $(LOG_FILE)
endif

# This generates normally distributed measurements and errors
# and logs the convolution of this to simulate a measurement
plot-test:
	../Scripts/gen_data.py
	[ $$? -eq 0 ] && $(COMMON)/plot.py -o $(PLOTS_FOLDER) \
	-x_min $(DEFAULT_PLOT_X_MIN) \
	-x_range $(DEFAULT_PLOT_RANGE_X) $(LOG_FILE)

parse-cmov-prep:
	../Scripts/gen_secret.py -p $(SECRET_IN) \
				$(shell expr $(NUM) / $(NUM_POOR_MANS_CMOV) )

parse-cmov: clean parse-cmov-prep run-no-clean
	../Scripts/parse_poor_mans_cmov.py -n $(NUM) -b 6 -a 4 \
				$(LOG_FILE) $(SECRET_IN)
	#../Scripts/parse_poor_mans_cmov.py -n $(NUM) -b 2 -a 50 \

$(OUTPUT): $(BUILDDIRS) $(OBJECTS)
	echo "$(INDENT)[LD]" $(OBJECTS) $(EXTRA_OBJECTS) $(LIBS) -o $(OUTPUT)
	$(LD) $(OBJECTS) $(EXTRA_OBJECTS) $(LDFLAGS) $(PCMLDFLAGS) asm_LONG_NOP.o -o $(OUTPUT) 


main.o : FORCE
FORCE:

%.o : %.c
	echo "$(INDENT)[===] . [===]"
	echo "$(INDENT)[CC] " $<
	$(CC) $(CFLAGS) $(INCLUDE) -c $<

%.o : %.S
	echo "$(INDENT)[AS] " $<
	$(AS) $(ASFLAGS) $(INCLUDE) -c $< -o $@

clean: $(CLEANDIRS)
	echo "$(INDENT)[RM]" $(OBJECTS) $(OUTPUT)
	rm -f $(OBJECTS) $(OUTPUT)
	rm -f $(LOGS)
	rm -f $(SECRET_IN)

$(BUILDDIRS):
	echo "$(INDENT)[===] $(@:build-%=%) [===]"
	$(MAKE) -C $(@:build-%=%) INDENT+="$(INDENT_STEP)" M32=$(M32) curr-dir=$(curr-dir)/$(@:build-%=%)

$(CLEANDIRS):
	echo "$(INDENT)[===] $(@:clean-%=%) [===]"
	$(MAKE) clean -C $(@:clean-%=%) INDENT+="$(INDENT_STEP)" curr-dir=$(curr-dir)/$(@:build-%=%)
