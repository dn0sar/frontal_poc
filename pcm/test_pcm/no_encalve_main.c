/*
 *  This file is part of the SGX-Step enclave execution control framework.
 *
 *  Copyright (C) 2017 Jo Van Bulck <jo.vanbulck@cs.kuleuven.be>,
 *                     Raoul Strackx <raoul.strackx@cs.kuleuven.be>
 *
 *  SGX-Step is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  SGX-Step is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with SGX-Step. If not, see <http://www.gnu.org/licenses/>.
 */

#include <sgx_urts.h>
#include "Enclave/encl_u.h"
#include <signal.h>
#include <unistd.h>
#include <pwd.h>
#include <sys/klog.h>
#include "libsgxstep/apic.h"
#include "libsgxstep/cpu.h"
#include "libsgxstep/pt.h"
#include "libsgxstep/sched.h"
#include "libsgxstep/enclave.h"
#include "libsgxstep/debug.h"
#include "libsgxstep/config.h"
#include "libsgxstep/idt.h"

// Performance counters measurement
#if PCM_ENABLED
#include "pcm/perf_counters.h"
#endif

#include "Common/instr_lib.h"
#include "Common/init_encl_lib.h"

#define EDBGRD         0

#define LOG_FILE_PATH       "./logs/microbenchmark_cycles.log"
#define PREP_LOG_FILE_PATH  "./logs/prep_microbenchmark_cycles.log"
#define SECRET_INPUT_PATH   "./logs/secret_input.txt"

#define ZERO_STEP_PERCENTAGE 10

#define PAGE_SIZE       4096
#define PAGES_PER_PMD   512

// Constants for dmesg
#define SYSLOG_ACTION_READ_CLEAR    4
#define SYSLOG_ACTION_CLEAR         5
#define DMESG_LINE_SIZE             80
#define DMESG_BUF_SIZE              (10 * DMESG_LINE_SIZE)

sgx_enclave_id_t eid;
int do_irq, fault_cnt;
uint64_t irq_cnt;
uint64_t *pmd_encl;

uint8_t *do_cnt_instr;
uint8_t do_cnt_instr_old;
uint8_t remaining_prep_instr;
uint8_t remaining_init_prep_instr;
uint8_t curr_idx;
uint8_t log_zero_steps;

uint64_t cycles_cnt;
uint64_t tot_cycles_cnt;
uint64_t instr_cnt;
uint64_t tot_instr;
uint64_t zero_step_cnt;
uint64_t tot_zero_steps;

FILE *log_fp;

#if LOG_PREP_INSTRS
    FILE *prep_log_fp;

    uint64_t *prep_log_arr;
    uint32_t prep_log_arr_size;
    uint32_t *prep_offset_arr;
#endif

uint64_t pte_encl_len;
uint64_t pte_encl_arr_len;
uint64_t pte_encl_next_idx;
uint64_t *curr_pte_encl;
uint64_t *next_pte_encl;
uint64_t **pte_encl_arr;
void *code_adrs;
void *code_end_adrs;

typedef struct measurement_t {
    uint64_t cycles;
    uint32_t page_nr;
    uint8_t accessed;
#if PCM_ENABLED
    uint64_t pcms[4];
#endif
} measurement;
measurement *log_arr;

#if PCM_ENABLED
uint64_t pcms_before[4] = {0, 0, 0, 0};
#endif

uint64_t log_arr_size;
uint64_t log_arr_idx;

char *dmesg_bufp;
char *code_adrs_str;


extern void asm_microbenchmark( uint8_t *do_cnt_instr );

/* ======================= HELPER FUNCTIONS ======================= */
void log_test_info(uint8_t idx)
{
    fprintf(log_fp, "Testing instruction %s (runs: %d, interval: %d, part: %d/%d)\n",
            tested_instr_names[idx], NUM_RUNS, SGX_STEP_TIMER_INTERVAL, 
            idx + 1, nr_of_parts);
}

#if LOG_PREP_INSTRS
void log_prep_instrs()
{
    int i, j, k;
    uint32_t idx;

    for (i = 0; i < nr_of_parts; ++i) {
        fprintf(prep_log_fp, "Log %d prepare instructions for %s\n",
                nr_of_prep_instr[i], tested_instr_names[i]);

        for (j = 0; j < nr_of_prep_instr[i]; ++j) {
            fprintf(prep_log_fp, "Prepare instruction number %d\n", j);

            for (k = 0; k < NUM_RUNS; ++k) {
                idx = prep_offset_arr[i] + j * NUM_RUNS + k;
                fprintf(prep_log_fp, "%lu\n", prep_log_arr[idx]);
            }
        }
    }
}
#endif

void init_time_measurement() 
{
    int i;

    tot_cycles_cnt  = 0;
    tot_zero_steps  = 0;
    instr_cnt       = 0;

    ASSERT( do_cnt_instr    = (uint8_t *) calloc( 1, sizeof(uint8_t) ) );
    do_cnt_instr_old = 0;

    curr_idx                    = 0;
    remaining_init_prep_instr   = nr_of_init_prep_instr[curr_idx];
    remaining_prep_instr        = nr_of_prep_instr[curr_idx];
    tot_instr                   = nr_of_parts * NUM_RUNS;

    log_arr_size = 0;
    for (i = 0; i < nr_of_parts; ++i) {
        log_arr_size += nr_of_init_prep_instr[i] 
                            + NUM_RUNS * (nr_of_prep_instr[i] + 1);
    }
    log_arr_size = (log_arr_size * (100 + ZERO_STEP_PERCENTAGE) ) / 100;

    ASSERT( log_arr = (measurement *) calloc( log_arr_size, sizeof(measurement) ) );

    ASSERT( log_fp = fopen(LOG_FILE_PATH, "w") );
    fprintf(log_fp, "Test name addition: %s\n", test_name_addition);

    #if LOG_PREP_INSTRS
        ASSERT( prep_offset_arr = (uint32_t *) calloc( nr_of_parts, sizeof(uint32_t) ));

        prep_log_arr_size   = 0;
        for (i = 0; i < nr_of_parts; ++i) {
            prep_offset_arr[i] = prep_log_arr_size;
            prep_log_arr_size += NUM_RUNS * nr_of_prep_instr[i];
        }

        ASSERT( prep_log_arr = (uint64_t *) calloc( prep_log_arr_size, 
                                                    sizeof(uint64_t) ) );

        ASSERT( prep_log_fp = fopen(PREP_LOG_FILE_PATH, "w") );
    #endif

    #if LOG_ZERO_STEPS
        log_zero_steps = LOG_ZERO_STEPS;
        fprintf(log_fp, "Measuring %d zero steps\n", ZERO_STEPS_NUM);

        ASSERT( dmesg_bufp = (char *) calloc(1, DMESG_BUF_SIZE + 1) );
        ASSERT( code_adrs_str = (char *) calloc(1, DMESG_LINE_SIZE) );
    #else
        log_zero_steps = 0;
    #endif
}

void init_encl_vars()
{
    eid = 0;
    
    irq_cnt     = 0;
    do_irq      = 1; 
    fault_cnt   = 0;
    
    pmd_encl        = NULL;
    curr_pte_encl   = NULL;
    next_pte_encl   = NULL;
}

void analyze_cycles(measurement *msrmnt)
{
    uint64_t cycles_cnt = msrmnt-> cycles;
    uint32_t page_nr = msrmnt -> page_nr;
#if PCM_ENABLED
    uint64_t *pcms = msrmnt -> pcms;
#endif

    if (remaining_init_prep_instr) {
        --remaining_init_prep_instr;
        return;
    }
    else if (remaining_prep_instr) {
        #if LOG_PREP_INSTRS
            // Group the prep instructions for each instruction (instr 1, prep 1; 
            // instr1, prep2; .. ; instrX, prep1; .. instrX, prepY)
            uint32_t prep_idx = prep_offset_arr[curr_idx] +
                                (nr_of_prep_instr[curr_idx] -
                                remaining_prep_instr) * NUM_RUNS 
                                + (instr_cnt % NUM_RUNS);

            prep_log_arr[ prep_idx ] = cycles_cnt;
        #endif

        --remaining_prep_instr;
        return;
    }

    tot_cycles_cnt += cycles_cnt;
    ++instr_cnt;
    
    fprintf(log_fp, "%lu, %u", cycles_cnt, page_nr);
#if PCM_ENABLED
    fprintf(log_fp, ", %lu, %lu, %lu, %lu", pcms[0], pcms[1], pcms[2], pcms[3]);
#endif
    fprintf(log_fp, "\n");

    // Macro if case to suppress div by zero warnings
    #if (NUM_RUNS > 0)
    if (instr_cnt % NUM_RUNS == 0) {
        if (instr_cnt != tot_instr) {
            ++curr_idx;
            log_test_info(curr_idx);
            remaining_init_prep_instr = nr_of_init_prep_instr[curr_idx];
        }
        else {
            return;
        }
    }
    #endif
    remaining_prep_instr = nr_of_prep_instr[curr_idx];
}

void analyze_measurement(measurement *msrmnt) 
{
    if (msrmnt->accessed)
    {
        if (instr_cnt == tot_instr) {
            error("Trailing instructions measured, check if e.g. an init instruction "
                  "takes more than one execution step");
            exit(1);
        }
        analyze_cycles(msrmnt);
    }
    else {
        ++tot_zero_steps;
    }
}

/* 
 * Log zero steps, prepare instructions and test instructions from
 * memory to files.
 * Free allocated data structures
 */
void finish_time_measurement()
{
    int i;

    #if LOG_ZERO_STEPS
        free(dmesg_bufp);
        free(code_adrs_str);
    #endif

    #if (NUM_RUNS > 0)
        log_test_info(curr_idx);
    #endif

    for(i = 0; i < log_arr_idx; ++i) {
        analyze_measurement( log_arr + i );
    }

    #if LOG_PREP_INSTRS
        log_prep_instrs();

        fclose(prep_log_fp);
        free(prep_log_arr);
        free(prep_offset_arr);
    #endif

    fclose(log_fp);
    free(log_arr);
    free(do_cnt_instr);
}

void encl_vars_cleanup()
{
    free(pte_encl_arr);
}

inline uint64_t cmov64(uint8_t pred, uint64_t source, uint64_t new_val)
{
    __asm__(
        "testb %1, %1;"
        "cmovnzq %2, %0;"
        : "+r"(source)
        : "r"(pred), "r"(new_val)
        : "cc");
    return source;
}

/* ===================== END HELPER FUNCTIONS ===================== */


/* ================== ATTACKER IRQ/FAULT HANDLERS ================= */

/* Called before resuming the enclave after an Asynchronous Enclave eXit. */
void aep_cb_func(void)
{
    uint8_t accessed;
    uint8_t accessed_next;
    uint8_t cnt_instr;
#if PCM_ENABLED
    uint64_t pcms[4];
    pcms[0] = pcm_c_get_core_event_fast(VICTIM_CPU,0) - pcms_before[0];
    pcms[1] = pcm_c_get_core_event_fast(VICTIM_CPU,1) - pcms_before[1];
    pcms[2] = pcm_c_get_core_event_fast(VICTIM_CPU,2) - pcms_before[2];
    pcms[3] = pcm_c_get_core_event_fast(VICTIM_CPU,3) - pcms_before[3];
#endif        

    #if EDBGRD
        uint64_t erip = edbgrd_erip() - (uint64_t) get_enclave_base();
        info("^^ enclave RIP=%#llx; ACCESSED=%d", erip, ACCESSED(*curr_pte_encl));
    #endif
    irq_cnt++;

    /* Only count instructions if do_cnt_instr was set to true in the previous 
     * call (not in this one, since then you count the instruction that sets it 
     * to true)
     */
    cnt_instr = *do_cnt_instr && do_cnt_instr_old == *do_cnt_instr;

    /* Keep this function constant time in most cases so that it does
     * not disturb measurements. We found that measurements after shorter
     * function calls are faster. This is probably due to cache lines that
     * get evicted if you do more and take longer in this function here
     *
     * However, the two ifs below are ok, because the first is an error
     * that terminates the program after if was executed once and the second
     * is only false before and after all measurements, so it is still constant
     * time during the measurement phase
     */
    if ( __builtin_expect(log_arr_size != 0 && log_arr_idx >= log_arr_size, 0) ) 
    {
        error("Unexpected high number of zero steps. Try adjusting the APIC timer "
              "interval or increase ZERO_STEP_PERCENTAGE.");
        exit(1);
    }
    else if ( __builtin_expect( cnt_instr, 1 ) ) 
    {
        ASSERT( curr_pte_encl );
        ASSERT( next_pte_encl );
        accessed_next = ACCESSED( *next_pte_encl );
        accessed = ACCESSED( *curr_pte_encl ) || accessed_next;

        // Constant time update variables if we move to next page (instead of an if)
        curr_pte_encl       = (uint64_t *) cmov64(accessed_next, 
                                            (uint64_t) curr_pte_encl, 
                                            (uint64_t) next_pte_encl); 
        next_pte_encl       = (uint64_t *) cmov64(accessed_next, 
                                            (uint64_t) next_pte_encl, 
                                            (uint64_t) pte_encl_arr[pte_encl_next_idx]);
        pte_encl_next_idx   = cmov64(accessed_next, 
                                    pte_encl_next_idx, 
                                    pte_encl_next_idx + 1);
        
        cycles_cnt = ((uint64_t) tsc_aex_upper << 32 | tsc_aex_lower) 
                     - ((uint64_t) tsc_eresume_upper << 32 | tsc_eresume_lower);


        log_arr[log_arr_idx] = (measurement) {
            cycles_cnt,
            pte_encl_next_idx - 1,
            accessed, 
#if PCM_ENABLED
            pcms[0],
            pcms[1],
            pcms[2],
            pcms[3]
#endif
        };

        log_arr_idx += 1;
    }

    do_cnt_instr_old = *do_cnt_instr;

    /* End of custom code */

    // Again unlikely to be taken, so ok if not constant
    if ( __builtin_expect( cnt_instr && do_irq && 
                            (irq_cnt > (uint64_t) NUM_RUNS*500), 0 ) )
    {
        warning("excessive interrupt rate detected (try adjusting timer interval " \
             "to avoid getting stuck in zero-stepping); aborting...");
	    do_irq = 0;
    }

#if PCM_ENABLED
    pcms_before[0] = pcm_c_get_core_event_fast(VICTIM_CPU,0);
    pcms_before[1] = pcm_c_get_core_event_fast(VICTIM_CPU,1);
    pcms_before[2] = pcm_c_get_core_event_fast(VICTIM_CPU,2);
    pcms_before[3] = pcm_c_get_core_event_fast(VICTIM_CPU,3);
#endif    

    /*
     * NOTE: We explicitly clear the "accessed" bit of the _unprotected_ PTE
     * referencing the enclave code page about to be executed, so as to be able
     * to filter out "zero-step" results that won't set the accessed bit.
     */
    *curr_pte_encl = MARK_NOT_ACCESSED( *curr_pte_encl );
    *next_pte_encl = MARK_NOT_ACCESSED( *next_pte_encl );

    /*
     * Configure APIC timer interval for next interrupt.
     *
     * On our evaluation platforms, we explicitly clear the enclave's
     * _unprotected_ PMD "accessed" bit below, so as to slightly slow down
     * ERESUME such that the interrupt reliably arrives in the first subsequent
     * enclave instruction.
     * 
     */
    // Branch always taken during measurements.
    if ( __builtin_expect(do_irq, 1) )
    {
        ASSERT(pmd_encl);
        *pmd_encl = MARK_NOT_ACCESSED( *pmd_encl );

        // Make sure currently used page is prefetched
        // (usually this is the case anyways)
        // Note: Prefetching next page is a bad idea, since this sometimes
        // evicts data used by the enclave which creates double peaks.
        __asm__ __volatile__(
            "prefetcht0 (curr_pte_encl)\n\t"
            :::
        );
        // Serializing helps to reduce variance
        __asm__ __volatile__("cpuid" :::);
        /* 
         * -------------------------------------------------- 
         * NEVER add code below this line, otherwise the 
         * interrupt will arrive too early (during ERESUME) 
         * -------------------------------------------------- 
         */
        apic_timer_irq( SGX_STEP_TIMER_INTERVAL );
    }
}

/* Called upon SIGSEGV caused by untrusted page tables. */
void fault_handler(int signal)
{
    uint32_t tsc_page_fault_upper;
    uint32_t tsc_page_fault_lower;

    int ret_code;
    char* next_line_ptr;
    char* curr_dmesg_bufp;

            
    // To log zero steps, leave code not executable
    if (log_zero_steps) 
    {
        fault_cnt++;

        // First measurement is invalid, since timer was not started
        if (fault_cnt > 1) 
        {
            // HACK: Store register values to restore AEX synthetic register state
            // again
            __asm__ __volatile__(
                "mov %%rcx, %%r14\n\t"
                "mov %%rbx, %%r15\n\t"
                ::: "%r14", "%r15"
            );

            // The second time stamp was logged by the modified page fault handler 
            // to dmesg, so we need to parse dmesg to get it
            klogctl(SYSLOG_ACTION_READ_CLEAR, dmesg_bufp, DMESG_BUF_SIZE);
            curr_dmesg_bufp = dmesg_bufp;

            // Parse kernel log line by line, in case there are multiple
            // log entries, take the first one that appears, which is the newest
            while (ret_code != 2 && curr_dmesg_bufp != NULL)
            {
                next_line_ptr = strchr(dmesg_bufp, '\n');
    
                if (next_line_ptr) {
                    *next_line_ptr = '\0';
                }

                if ( strstr(curr_dmesg_bufp, code_adrs_str) ) {
                    // Ignore log timestamp, then parse lower and upper bits of the 
                    // processor timestamp
                    ret_code = sscanf(curr_dmesg_bufp, "%*[^P]PFT: %x %x", 
                                      &tsc_page_fault_lower, &tsc_page_fault_upper);
                }

                curr_dmesg_bufp = next_line_ptr ? (next_line_ptr + 1) : NULL;
            }
            
            // Throw error if not two variables were matched
            if (ret_code != 2) {
                error("Failed to parse dmesg with return code %d", ret_code);
            }

            cycles_cnt = ((uint64_t) tsc_page_fault_upper << 32 | tsc_page_fault_lower) 
                         - ((uint64_t) tsc_eresume_upper << 32 | tsc_eresume_lower);

            fprintf(log_fp, "%lu\n", cycles_cnt);

            // + 1 because we cannot measure the first zero step, since the timer
            // was not started yet
            if (fault_cnt >= ZERO_STEPS_NUM + 1) {
                log_zero_steps  = 0;
                fault_cnt       = 0;

                // Now register the normal callback
                info("Finish zero step measuring, register callback");
                register_aep_cb(aep_cb_func);
            }

            // HACK: Restore AEX synthetic register state (otherwise you get a segfault)
            __asm__ __volatile__(
                "mov $3, %%rax\n\t"
                "mov $0, %%rdx\n\t"
                "mov %%r14, %%rcx\n\t"
                "mov %%r15, %%rbx\n\t"
                "mov $0, %%r14\n\t"
                "mov $0, %%r15\n\t"
                // Prefetch current page
                "prefetcht0 (curr_pte_encl)\n\t"
                ::: "%rax", "%rdx", "%rcx", "%rbx", "%r14", "%r15"
            );
        }
        else {
            // Have to clear the log, otherwise this entry will always appear
            klogctl(SYSLOG_ACTION_CLEAR, NULL, 0);
        }
    }

    // When not logging zero steps (or stopped doing so), initialize single stepping
    if (!log_zero_steps) 
    {
        #if !(POOR_MANS_CMOV)
            info("Caught fault %d! Restoring enclave page permissions..", signal);
        #endif

        *curr_pte_encl = MARK_NOT_EXECUTE_DISABLE(*curr_pte_encl);

        *curr_pte_encl = MARK_NOT_ACCESSED( *curr_pte_encl );
        *next_pte_encl = MARK_NOT_ACCESSED( *next_pte_encl );

        ASSERT(fault_cnt++ < 10);
    }

    // NOTE: return eventually continues at aep_cb_func and initiates
    // single-stepping mode.
}

int irq_count = 0;

void irq_handler(uint8_t *rsp)
{
    uint64_t *p = (uint64_t*) rsp;
#if 0
    printf("\n");
    info("****** hello world from user space IRQ handler with count=%d ******",
        irq_count++);

    info("APIC TPR/PPR is %d/%d", apic_read(APIC_TPR), apic_read(APIC_PPR));
    info("RSP at %p", rsp);
    info("RIP is %p", *p++);
    info("CS is %p", *p++);
    info("EFLAGS is %p", *p++);
#endif
}

/* ================== ATTACKER INIT/SETUP ================= */

/* Configure and check attacker untrusted runtime environment. */
void attacker_config_runtime(void)
{
    ASSERT( !claim_cpu(VICTIM_CPU) );
    ASSERT( !prepare_system_for_benchmark(PSTATE_PCT) );
    ASSERT(signal(SIGSEGV, fault_handler) != SIG_ERR);
	print_system_settings();

    if (isatty(fileno(stdout)))
    {
        warning("Interactive terminal detected; known to cause "
                "unstable timer intervals! Use stdout file redirection for "
                "precise single-stepping results...");
    }

    // Register the callback later when we count zero steps to first have an
    // empty small, constant callback function.
    #if !LOG_ZERO_STEPS
        register_aep_cb(aep_cb_func);
    #endif
    //register_enclave_info();
    //print_enclave_info();
}

// Setup the page tracking, make the first one not executable to trigger single
// stepping
void prepare_single_stepping(void)
{
    curr_pte_encl       = pte_encl_arr[0];
    next_pte_encl       = pte_encl_arr[1];
    pte_encl_next_idx   = 2;

    #if SINGLE_STEP_ENABLE
        *curr_pte_encl = MARK_EXECUTE_DISABLE( *curr_pte_encl );
    #endif
}

/* Provoke page fault on enclave entry to initiate single-stepping mode. */
void attacker_config_page_table(void)
{
    uint64_t i;

    #if POOR_MANS_CMOV
        SGX_ASSERT( get_asm_poor_mans_cmov_adrs(eid, &code_adrs) );
        SGX_ASSERT( get_asm_poor_mans_cmov_end_adrs(eid, &code_end_adrs) );
    #else
        SGX_ASSERT( get_asm_microbenchmark_adrs(eid, &code_adrs) );
        SGX_ASSERT( get_asm_microbenchmark_end_adrs(eid, &code_end_adrs) );
    #endif

    #if LOG_ZERO_STEPS
        sprintf(code_adrs_str, "%llx", code_adrs);
    #endif

    info("enclave trigger code adrs at %p\n", code_adrs);
    
    pte_encl_len = 1 + ( (uint64_t) code_end_adrs - (uint64_t) code_adrs ) 
                    / PAGE_SIZE;

    //print_page_table( code_adrs );
    if ( pte_encl_len > 1) 
    {
        if ( pte_encl_len > PAGES_PER_PMD ) {
            warning("Test code fills more than %d pages, i.e. more than one PMD "
                    "(%lu pages)", PAGES_PER_PMD, pte_encl_len);
        }   
        else {
            warning("Test code fills more than one page (%lu pages)", pte_encl_len);
        }
    }

    // Last page will not contain code anymore
    pte_encl_arr_len = pte_encl_len + 1;
    ASSERT( pte_encl_arr = (uint64_t **) calloc(pte_encl_arr_len, 
                                                sizeof(uint64_t *) ) );

    for (i = 0; i < pte_encl_arr_len; ++i) {
        ASSERT( pte_encl_arr[i] = (uint64_t *) remap_page_table_level(code_adrs, PTE) );
        code_adrs += PAGE_SIZE;
    }

    prepare_single_stepping();

    //print_page_table( get_enclave_base() );
    ASSERT( pmd_encl = (uint64_t *) remap_page_table_level( get_enclave_base(), PMD) );
}


#if PCM_ENABLED
int perf_counter_init(int argc, const char **argv) {
    //for (int i = 1; i < argc; i++) {
        //TODO: argc should be at most 4
        //pcm_c_build_core_event(0, "event=0xcb,umask=0x01"); // HW_INTERRUPTS.RECEIVED
        pcm_c_add_core_event("event=0xb1,umask=0x10"); //UOPS_EXECUTED.X87
        //pcm_c_build_core_event(1, "event=0xc1,umask=0xfe"); // Alternative PEBS X87 OPS
        pcm_c_add_core_event("event=0xc2,umask=0x02,inv=0x1,cmask=0x10");
    //}
    int result = pcm_c_init();
    if (result != 0) {
        printf("Couldn't init perf counters.. Bye\n");
        return -1;
    }
    pcm_c_start();
    return 0;
}
#endif

/* ================== ATTACKER MAIN ================= */

/* Untrusted main function to create/enter the trusted enclave. */
int main( int argc, const char **argv )
{
    uint8_t some_val = 0;
    int i = 0;

#if PCM_ENABLED
    if (perf_counter_init(argc, argv)) return -1;
#endif
    ASSERT( !claim_cpu(VICTIM_CPU) );
   

    for (i = 0; i < 4; i++) { 
        pcms_before[i] = pcm_c_get_core_event_fast(VICTIM_CPU,i);
    }

    asm_microbenchmark(&some_val);

    for (i = 0; i < 4; i++) { 
        pcms_before[i] = pcm_c_get_core_event_fast(VICTIM_CPU,i) - pcms_before[i];
    }
    // Call prepare_instr_config first, other functions need those values

    
    for (i = 0; i < 4; i++) { 
        printf("Event %d: %llu\n", i, pcms_before[i]);
    }

    info_event("all done; counted %lu IRQs", irq_cnt);

#if PCM_ENABLED
    pcm_c_clean();
#endif
}
