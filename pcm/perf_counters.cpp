#include "cpucounters.h"
#include "utils.h"

#include "perf_counters.h"

using namespace std;                                                                                                                                                                                                                                  

void build_event(const char * argv, EventSelectRegister *reg, int idx, int os_def = 1);

struct CoreEvent                                                                                                                                                                                                                                      
{
    char name[256];
    uint64 value;
    uint64 msr_value;
    char * description;
} events[4];

extern "C" {
    SystemCounterState SysBeforeState, SysAfterState;
    std::vector<CoreCounterState> BeforeState, AfterState;
    std::vector<SocketCounterState> DummySocketStates;
    EventSelectRegister regs[PERF_MAX_COUNTERS];
    PCM::ExtendedCustomCoreEventDescription conf;
    int event_index = 0;

    int pcm_c_add_core_event(const char * argv)
    {
        if(event_index > 3)
            return -1;

#ifndef PCM_SILENT
        cout << "building core event " << argv << " " << event_index << endl;
#endif
        build_event(argv, &regs[event_index], event_index, 0);
        event_index++;
        return 0;
    }

    int pcm_c_get_number_of_set_events() {
        return event_index;
    }

    int pcm_c_get_max_supported_counters() {
        PCM * m = PCM::getInstance();
        return m->getMaxCustomCoreEvents();
    }

    int pcm_c_init()
    {
        // We don't want the perf counter to mess up with our signals in SGX step, so we install our own signal handlers
        //set_signal_handlers();
        PCM * m = PCM::getInstance();
        conf.fixedCfg = NULL; // default
        conf.nGPCounters = m->getMaxCustomCoreEvents();
        conf.gpCounterCfg = regs;
        conf.OffcoreResponseMsrValue[0] = events[0].msr_value;
        conf.OffcoreResponseMsrValue[1] = events[1].msr_value;

        m->resetPMU();
        PCM::ErrorCode status = m->program(PCM::EXT_CUSTOM_CORE_EVENTS, &conf);
        if(status == PCM::Success)
            return 0;
        else
            return -1;
    }

    void pcm_c_start()
    {
        PCM * m = PCM::getInstance();
        m->getAllCounterStates(SysBeforeState, DummySocketStates, BeforeState);
    }

    void pcm_c_stop()
    {
        PCM * m = PCM::getInstance();
        m->getAllCounterStates(SysAfterState, DummySocketStates, AfterState);
    }

    void pcm_c_clean() {
        exit_cleanup(false);
    }

    uint64_t pcm_c_get_cycles(uint32_t core_id)
    {
        return getCycles(BeforeState[core_id], AfterState[core_id]);
    }

    uint64_t pcm_c_get_instr(uint32_t core_id)
    {
        return getInstructionsRetired(BeforeState[core_id], AfterState[core_id]);
    }

    uint64_t pcm_c_get_core_event(uint32_t core_id, uint32_t event_id)
    {
        return getNumberOfCustomEvents(event_id, BeforeState[core_id], AfterState[core_id]);
    }
    
    uint64_t pcm_c_get_core_event_fast(uint32_t core_id, uint32_t event_id) {
        PCM * m = PCM::getInstance();
        return m->getCustomCoreEvent(core_id, event_id);
    }

}

// emulates scanf %i for hex 0x prefix otherwise assumes dec (no oct support)
bool match(const char * subtoken, const char * name, int * result)
{
    std::string sname(name);
    if (pcm_sscanf(subtoken) >> s_expect(sname + "0x") >> std::hex >> *result)
        return true;

    if (pcm_sscanf(subtoken) >> s_expect(sname) >> std::dec >> *result)
        return true;

    return false;
}

#define EVENT_SIZE 256
void build_event(const char * argv, EventSelectRegister *reg, int idx, int os_def)
{
    char *token, *subtoken, *saveptr1, *saveptr2;
    char name[EVENT_SIZE], *str1, *str2;
    int j, tmp;
    uint64 tmp2;
    reg->value = 0;
    reg->fields.usr = 1;
    reg->fields.os = os_def;
    reg->fields.enable = 1;

    memset(name,0,EVENT_SIZE);
#ifdef _MSC_VER
    strncpy_s(name, argv, EVENT_SIZE - 1);
#else
    strncpy(name,argv,EVENT_SIZE-1); 
#endif
    /*
       uint64 apic_int : 1;

       offcore_rsp=2,period=10000
       */
    for (j = 1, str1 = name; ; j++, str1 = NULL) {
        token = strtok_r(str1, "/", &saveptr1);
        if (token == NULL)
            break;
        
        if(strncmp(token,"cpu",3) == 0)
            continue;

        for (str2 = token; ; str2 = NULL) {
            tmp = -1;
            subtoken = strtok_r(str2, ",", &saveptr2);
            if (subtoken == NULL)
                break;
            if(match(subtoken,"event=",&tmp))
                reg->fields.event_select = tmp;
            else if(match(subtoken,"umask=",&tmp))
                reg->fields.umask = tmp;
            else if(strcmp(subtoken,"edge") == 0)
                reg->fields.edge = 1;
            else if(match(subtoken,"any=",&tmp))
                reg->fields.any_thread = tmp;
            else if(match(subtoken,"inv=",&tmp))
                reg->fields.invert = tmp;
            else if(match(subtoken, "os=",&tmp))
                reg->fields.os = tmp;
            else if(match(subtoken, "usr=",&tmp))
                reg->fields.usr = tmp;
            else if(match(subtoken,"cmask=",&tmp))
                reg->fields.cmask = tmp;
            else if(match(subtoken,"in_tx=",&tmp))
                reg->fields.in_tx = tmp;
            else if(match(subtoken,"in_tx_cp=",&tmp))
                reg->fields.in_txcp = tmp;
            else if(match(subtoken,"pc=",&tmp))
                reg->fields.pin_control = tmp;
            else if(match(subtoken,"msr_pebs_frontend=", &tmp)) {
                reg->is_pebs = true;
                reg->use_frontend_ret = true;
                reg->frontend_ret = tmp;
            }
            else if(pcm_sscanf(subtoken) >> s_expect("offcore_rsp=") >> std::hex >> tmp2) {
                if(idx >= 2)
                {
                    cerr << "offcore_rsp must specify in first or second event only. idx=" << idx << endl;
                    throw idx;
                }
                events[idx].msr_value = tmp2;
            }
            else if(pcm_sscanf(subtoken) >> s_expect("name=") >> setw(255) >> events[idx].name) ;
            else
            {
                cerr << "Event '" << subtoken << "' is not supported. See the list of supported events"<< endl;
                throw subtoken;
            }

        }
    }
    events[idx].value = reg->value;
}
