#ifndef __cplusplus
#include <stdint.h>
#endif

#define PCM_DELAY_DEFAULT 1.0 // in seconds
#define PCM_DELAY_MIN 0.015 // 15 milliseconds is practical on most modern CPUs
#define PCM_CALIBRATION_INTERVAL 50 // calibrate clock only every 50th iteration
#define MAX_CORES 4096

#ifdef __cplusplus
extern "C" {
#endif
    int pcm_c_add_core_event(const char * argv);
    int pcm_c_get_number_of_set_events();
    int pcm_c_get_max_supported_counters();
    int pcm_c_init();
    void pcm_c_start();
    void pcm_c_stop();
    void pcm_c_clean();
    uint64_t pcm_c_get_cycles(uint32_t core_id);
    uint64_t pcm_c_get_cycles(uint32_t core_id);
    uint64_t pcm_c_get_core_event(uint32_t core_id, uint32_t event_id);
    uint64_t pcm_c_get_core_event_fast(uint32_t core_id, uint32_t event_id);
#ifdef __cplusplus
}
#endif
