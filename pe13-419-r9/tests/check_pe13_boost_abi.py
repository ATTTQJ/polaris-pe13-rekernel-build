"""Check that legacy boost parameters use the real modern parser and state."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from run_host_checks import function

ROOT=Path(__file__).resolve().parents[1]
MOCK=r'''
#undef NDEBUG
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <stddef.h>
#include <errno.h>
#include <sys/types.h>
#define PAGE_SIZE 4096
struct kobject { int unused; };
struct kobj_attribute { int unused; };
struct kernel_param { int unused; };
struct cpu_sync { unsigned input_boost_freq; };
static struct cpu_sync sync_info[8];
static bool input_boost_enabled;
#define per_cpu(s,i) s[i]
#define for_each_possible_cpu(i) for((i)=0;(i)<8;(i)++)
static unsigned num_possible_cpus(void) { return 8; }
static char *strnchr(const char *s,size_t n,char c) { for(size_t i=0;i<n&&s[i];i++)if(s[i]==c)return (char *)s+i;return NULL; }
'''
TEST=r'''
int main(void) {
    char text[PAGE_SIZE];
    assert(pe13_set_input_boost_freq("0:1324800",NULL)==0);
    assert(input_boost_enabled && sync_info[0].input_boost_freq==1324800 && sync_info[4].input_boost_freq==0);
    assert(pe13_get_input_boost_freq(text,NULL)>0 && strstr(text,"0:1324800 "));
    assert(pe13_set_input_boost_freq("0",NULL)==0 && !input_boost_enabled);
    assert(pe13_set_input_boost_freq("8:1000000",NULL)==-EINVAL);
    assert(pe13_set_input_boost_freq("invalid",NULL)==-EINVAL);
    assert(store_input_boost_freq(NULL,NULL,"1000000",7)==7);
    assert(pe13_get_input_boost_freq(text,NULL)>0 && strstr(text,"7:1000000 "));
    puts("PASS shared legacy/sysfs boost frequency state, PE13 init value, reset and parser errors");
}
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--kernel',type=Path,default=ROOT/'kernel-4.19')
    p.add_argument('--cc',nargs='+',default=[str(ROOT/'.tools/python/ziglang/zig.exe'),'cc'])
    args=p.parse_args();name='drivers/cpufreq/cpu-boost.c';text=(args.kernel/name).read_text()
    helpers=''.join(function(text,f) for f in ['store_input_boost_freq','show_input_boost_freq','pe13_set_input_boost_freq','pe13_get_input_boost_freq'])
    assert '#ifdef CONFIG_FSCRYPT_LEGACY_ICE_PE13\n/* PE13 init' in text
    for declaration in ['module_param_cb(input_boost_freq, &pe13_input_boost_freq_ops, NULL, 0644);',
                        'module_param(input_boost_ms, uint, 0644);','module_param(sched_boost_on_input, uint, 0644);']:
        assert declaration in text
    out=ROOT/'out/host-checks';out.mkdir(exist_ok=True);source=out/'pe13_boost_abi.c'
    source.write_text(MOCK+helpers+TEST,newline='\n');exe=out/('pe13_boost_abi'+('.exe' if sys.platform=='win32' else ''))
    subprocess.run(args.cc+['-std=gnu11','-O1','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(source),'-o',str(exe)],check=True)
    result=subprocess.check_output([str(exe)],text=True).strip();print(result)
    (out/'boost-abi-results.json').write_text(json.dumps({'scope':'Extracted real parser and legacy wrappers; not touch-input frequency or thermal validation','result':result,
        'source_sha256':{name:hashlib.sha256((args.kernel/name).read_bytes()).hexdigest()}},indent=2)+'\n')


if __name__=='__main__':
    main()
