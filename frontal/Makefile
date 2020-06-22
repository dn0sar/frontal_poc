LIBSGXSTEP_DIR       = ../sgx-step
LIBSGXSTEP           = $(LIBSGXSTEP_DIR)/libsgxstep
-include $(LIBSGXSTEP)/Makefile.config

ifeq ($(SGX_SDK),)
    SGX_SDK          = /opt/intel/sgxsdk
endif
export SGX_SDK
ifneq ($(SGX_SDK), /opt/intel/sgxsdk)
    URTS_LD_LIBRARY_PATH = LD_LIBRARY_PATH=$(LIBSGXSTEP_DIR)/linux-sgx/psw/urts/linux
endif

ENCLAVE              = Enclave
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
INCLUDE              = -I$(SGX_SDK)/include/ -I$(LIBSGXSTEP_DIR)
LDFLAGS             += -lsgx-step -lencl_proxy -lsgx_urts \
                       -lsgx_uae_service -pthread $(SUBDIRS:%=-L %) -L$(SGX_SDK)/lib$(LIB_SUFX)/ \
                       -L$(LIBSGXSTEP_DIR)/linux-sgx/psw/urts/linux

SOURCES              = $(shell ls *.c)
OBJECTS              = $(SOURCES:.c=.o)
OUTPUT               = app

BUILDDIRS            = $(SUBDIRS:%=build-%)
CLEANDIRS            = $(SUBDIRS:%=clean-%)

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

CFLAGS              += -DATTACK_SCENARIO=$(ATTACK_SCENARIO) -DNUM_RUNS=$(NUM) -DSGX_STEP_TIMER_INTERVAL=${SGX_STEP_TIMER_INTERVAL}

.SILENT:
.ONESHELL: run


all: $(OUTPUT)
	
run: clean all
	mkdir -p logs
	touch logs/out.txt
	tail -f logs/out.txt & TAIL_PID=$$!
	$(URTS_LD_LIBRARY_PATH) ./app > logs/out.txt || EXIT_CODE=$$?
	kill -TERM $$TAIL_PID
	exit $$EXIT_CODE

ifeq ($(ATTACK_SCENARIO),IPP_LIB)
parse: run
	./parse_ipp.py logs/measurements.txt > logs/ipp_meas.txt

plot: parse
	mkdir -p plots
	./plot.py -o plots logs/ipp_meas.txt
else
parse: run
	./parse.py -r ${NUM} -i ${NUM_INSTR}

plot: parse
	mkdir -p plots
	./plot.py -o plots logs/movs_0_${NUM}.log; done
	# The following will compute the success probability based on the first mov
	./attack_success.py -j 1 -s $$(( 2 * $(NUM_INSTR) + 1 )) -i 2 logs/measurements.txt logs/secrets.txt 

plot-all: SHELL:=/bin/bash
plot-all: parse
	mkdir -p plots
	for i in {1..${NUM_INSTR}}; do ./plot.py -o plots logs/movs_$$((i-1))_${NUM}.log; done
endif

$(OUTPUT): $(BUILDDIRS) $(OBJECTS)
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

$(BUILDDIRS):
	echo "$(INDENT)[===] $(@:build-%=%) [===]"
	$(MAKE) -C $(@:build-%=%) INDENT+="$(INDENT_STEP)" M32=$(M32) curr-dir=$(curr-dir)/$(@:build-%=%)

$(CLEANDIRS):
	echo "$(INDENT)[===] $(@:clean-%=%) [===]"
	$(MAKE) clean -C $(@:clean-%=%) INDENT+="$(INDENT_STEP)" curr-dir=$(curr-dir)/$(@:build-%=%)
