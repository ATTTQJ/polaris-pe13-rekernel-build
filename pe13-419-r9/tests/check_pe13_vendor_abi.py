"""Host-check real PE13 cache and UART helpers plus 64/32-bit ABI layouts.

DMA operations are mocked: this cannot prove physical cache coherence or radio
operation. Full kernel compilation and device tests are separately required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from run_host_checks import function

ROOT=Path(__file__).resolve().parents[1]
MOCK=r'''
#undef NDEBUG
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#ifndef EOPNOTSUPP
#define EOPNOTSUPP 95
#endif
#define IS_ENABLED(x) (x)
#define CONFIG_FSCRYPT_LEGACY_ICE_PE13 PROFILE
#define CONFIG_ION_FORCE_DMA_SYNC FORCE
#define ENOIOCTLCMD 515
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define GFP_KERNEL 0
static int subsys_ida;
static unsigned id_start,id_end;
static int ida_simple_get(int *ida,unsigned start,unsigned end,int gfp) {
    (void)ida;(void)gfp;id_start=start;id_end=end;return (int)start;
}
#define _IOWR(t,n,s) ((3U<<30)|((unsigned)sizeof(s)<<16)|((t)<<8)|(n))
#define _IOC_NR(c) ((c)&0xff)
static int fail_copy;
static void *compat_addresses[4];
static void *compat_ptr(unsigned long p) { return p<4?compat_addresses[p]:NULL; }
static int copy_from_user(void *d,const void *p,size_t n) {
    if(fail_copy || !p)return 1;memcpy(d,p,n);return 0;
}
#define __user
typedef int32_t compat_int_t;
typedef uint32_t compat_uptr_t;
typedef uint32_t compat_uint_t;
#define TTY_DRIVER_TYPE_SERIAL 1
#define TIOCPMGET 0x544D
#define TIOCPMPUT 0x544E
#define TIOCPMACT 0x544F
struct tty_driver { int type; const char *driver_name; };
struct tty_struct { struct tty_driver *driver; };
enum dma_data_direction { DMA_BIDIRECTIONAL, DMA_TO_DEVICE, DMA_FROM_DEVICE };
static const int dma_buf_ops=1, other_ops=2;
struct dma_buf { const void *ops; size_t size; };
static struct dma_buf buffer={&dma_buf_ops,4096};
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
static unsigned get_count, puts_count, operations;
static int injected_end, injected_begin;
static int events[8];
static struct dma_buf *dma_buf_get(int fd) { get_count++; return fd==17?&buffer:ERR_PTR(-EBADF); }
static void dma_buf_put(struct dma_buf *b) { assert(b==&buffer); puts_count++; }
static int __ion_dma_buf_end_cpu_access(struct dma_buf *b,enum dma_data_direction dir,bool mapped) {
    assert(b==&buffer && !mapped); events[operations++]=10+dir; return injected_end;
}
static int __ion_dma_buf_begin_cpu_access(struct dma_buf *b,enum dma_data_direction dir,bool mapped) {
    assert(b==&buffer && !mapped); events[operations++]=20+dir; return injected_begin;
}
'''
TEST=r'''
int main(void) {
    assert(sizeof(struct ion_pe13_flush_data)==24);
    assert(offsetof(struct ion_pe13_flush_data,vaddr)==8);
    assert(offsetof(struct ion_pe13_flush_data,offset)==16);
    assert(sizeof(struct compat_ion_pe13_flush_data)==20);
    assert(offsetof(struct compat_ion_pe13_flush_data,offset)==12);
    assert(sizeof(struct ion_pe13_custom_data)==16);
    assert(sizeof(struct compat_ion_pe13_custom_data)==8);
    const char *names[]={"spss","venus","ipa_fws","a630_zap","adsp","slpi","cdsp","modem","wil6210"};
    for(unsigned i=0;i<ARRAY_SIZE(names);i++) {
        assert(subsys_pe13_alloc_id(names[i])==(PROFILE?(int)i:0));
        assert(id_start==(PROFILE?i:0) && id_end==(PROFILE?i+1:0));
    }
    assert(subsys_pe13_alloc_id("unknown")== (PROFILE?9:0) && id_end==0);
    struct ion_pe13_flush_data f={.handle=17,.fd=0,.length=4096};
    struct ion_pe13_custom_data custom={ION_PE13_IOC_INV,(uintptr_t)&f};
    struct compat_ion_pe13_flush_data f32={.handle=17,.fd=0,.length=4096};
    struct compat_ion_pe13_custom_data c32={COMPAT_ION_PE13_IOC_INV,1};
    compat_addresses[1]=&f32;compat_addresses[2]=&c32;
    if(PROFILE) {
        int expected=FORCE?0:-EOPNOTSUPP;
        assert(ion_pe13_custom_ioctl(&custom)==expected);
        assert(compat_ion_pe13_cache_ioctl(COMPAT_ION_PE13_IOC_CUSTOM,2)==expected);
        assert(compat_ion_pe13_cache_ioctl(COMPAT_ION_PE13_IOC_INV,1)==expected);
        if(FORCE) {
            f.handle=0;f.fd=17; assert(ion_pe13_custom_ioctl(&custom)==0);
            f.handle=18;assert(ion_pe13_custom_ioctl(&custom)==-EBADF);f.handle=17;
            f.length=4097;assert(ion_pe13_custom_ioctl(&custom)==-EINVAL);f.length=4096;
        }
        fail_copy=1;assert(ion_pe13_custom_ioctl(&custom)==-EFAULT);
        assert(compat_ion_pe13_cache_ioctl(COMPAT_ION_PE13_IOC_CUSTOM,2)==-EFAULT);fail_copy=0;
        custom.cmd=0xc0184d03;assert(ion_pe13_custom_ioctl(&custom)==-ENOTTY);
        c32.cmd=0xc0144d03;assert(compat_ion_pe13_cache_ioctl(COMPAT_ION_PE13_IOC_CUSTOM,2)==-ENOIOCTLCMD);
        custom.cmd=ION_PE13_IOC_INV;custom.arg=0;assert(ion_pe13_custom_ioctl(&custom)==-EFAULT);
    } else {
        assert(ion_pe13_custom_ioctl(&custom)==-ENOTTY);
        assert(compat_ion_pe13_cache_ioctl(COMPAT_ION_PE13_IOC_CUSTOM,2)==-ENOIOCTLCMD);
    }
    get_count=puts_count=operations=0;
    struct tty_driver driver={TTY_DRIVER_TYPE_SERIAL,"msm_geni_serial_hs"};
    struct tty_struct tty={&driver};
    for (unsigned i=0;i<3;i++) assert(tty_pe13_geni_ioctl(&tty,0x5441+i)==(PROFILE?0x544D+i:0x5441+i));
    assert(tty_pe13_geni_ioctl(&tty,TIOCPMGET)==TIOCPMGET);
    assert(tty_pe13_geni_ioctl(&tty,0x1234)==0x1234);
    driver.type=2; assert(tty_pe13_geni_ioctl(&tty,0x5441)==0x5441); /* PTY remains untouched */
    driver.type=TTY_DRIVER_TYPE_SERIAL;driver.driver_name="other_serial";
    assert(tty_pe13_geni_ioctl(&tty,0x5441)==0x5441);
    driver.driver_name=NULL;assert(tty_pe13_geni_ioctl(&tty,0x5441)==0x5441);
    if (!PROFILE || !FORCE) {
        assert(ion_pe13_cache_sync(17,0,4096,2)==-EOPNOTSUPP);
        assert(get_count==0 && operations==0 && puts_count==0);
    } else {
        assert(ion_pe13_cache_sync(17,0,4096,0)==0 && operations==1 && events[0]==11);
        operations=0;assert(ion_pe13_cache_sync(17,128,512,1)==0 && operations==1 && events[0]==22);
        operations=0;assert(ion_pe13_cache_sync(17,0,4096,2)==0 && operations==2 && events[0]==10 && events[1]==20);
        operations=0;injected_end=-EPERM;
        assert(ion_pe13_cache_sync(17,0,4096,2)==-EPERM && operations==1);injected_end=0;
        operations=0;injected_begin=-EIO;
        assert(ion_pe13_cache_sync(17,0,4096,2)==-EIO && operations==2);injected_begin=0;
        operations=0;
        assert(ion_pe13_cache_sync(17,4097,1,2)==-EINVAL);
        assert(ion_pe13_cache_sync(17,4095,2,2)==-EINVAL);
        assert(ion_pe13_cache_sync(17,0xffffffffU,0xffffffffU,2)==-EINVAL);
        assert(ion_pe13_cache_sync(17,4096,0,2)==0);
        buffer.ops=&other_ops;assert(ion_pe13_cache_sync(17,0,1,2)==-EINVAL);buffer.ops=&dma_buf_ops;
        unsigned before_gets=get_count,before_puts=puts_count;
        assert(ion_pe13_cache_sync(17,0,1,3)==-EINVAL && get_count==before_gets && puts_count==before_puts);
        assert(ion_pe13_cache_sync(-1,0,1,2)==-EBADF && puts_count==before_puts);
        assert(operations==0 && get_count==puts_count+1); /* failed get has no reference */
    }
    puts("PASS native/compat direct and CUSTOM cache ABIs, handle priority, copy/command/range guards, UART isolation, SSR path IDs and refcounts");
}
'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--kernel',type=Path,default=ROOT/'kernel-4.19')
    parser.add_argument('--cc',nargs='+',default=[str(ROOT/'.tools/python/ziglang/zig.exe'),'cc'])
    args=parser.parse_args()
    paths=['drivers/tty/tty_io.c','drivers/staging/android/ion/ion.c',
        'drivers/staging/android/ion/ion_legacy.h','drivers/staging/android/ion/compat_ion.c',
        'drivers/staging/android/ion/ion-ioctl.c','drivers/soc/qcom/subsystem_restart.c']
    tty,ion,header,compat,ioctl,subsys=[(args.kernel/p).read_text() for p in paths]
    def structure(source,name):
        return re.search(r'struct '+name+r'\s*\{.*?\n\};',source,re.S)[0]+'\n'
    actual_tty=tty[tty.index('long tty_ioctl(struct file *file, unsigned int cmd, unsigned long arg)\n{'):]
    assert actual_tty.index('cmd = tty_pe13_geni_ioctl(tty, cmd);') < actual_tty.index('case TIOCGPTPEER:')
    assert 'case ION_PE13_IOC_CLEAN_INV:' in ioctl and 'ion_pe13_cache_flush(&data.pe13_flush, _IOC_NR(cmd))' in ioctl
    assert 'case COMPAT_ION_PE13_IOC_CLEAN_INV:' in compat and 'return compat_ion_pe13_cache_ioctl(cmd, arg);' in compat
    source=MOCK+structure(header,'ion_pe13_flush_data')+structure(compat,'compat_ion_pe13_flush_data')
    source+=structure(header,'ion_pe13_custom_data').replace('unsigned long arg','uintptr_t arg')+structure(compat,'compat_ion_pe13_custom_data')
    for text in (header,compat):
        source+='\n'.join(line for line in text.splitlines() if line.startswith('#define ') and 'ION_PE13_IOC_' in line)+'\n'
    source+=function(tty,'tty_pe13_geni_ioctl')+function(ion,'ion_pe13_cache_sync')
    source+=function(ion,'ion_pe13_cache_flush')+function(ioctl,'ion_pe13_custom_ioctl')
    source+=function(compat,'compat_ion_pe13_cache_ioctl')+function(subsys,'subsys_pe13_alloc_id')+TEST
    out=ROOT/'out/host-checks';out.mkdir(parents=True,exist_ok=True)
    file=out/'pe13_vendor_abi.c';file.write_text(source,newline='\n')
    results=[]
    for profile,force in [(0,0),(0,1),(1,0),(1,1)]:
        exe=out/(f'pe13_vendor_abi{profile}{force}'+('.exe' if sys.platform=='win32' else ''))
        subprocess.run(args.cc+['-std=gnu11','-O1','-Wall','-Wextra','-Werror','-Wno-unused-function',
            '-Wno-unused-parameter',f'-DPROFILE={profile}',f'-DFORCE={force}',str(file),'-o',str(exe)],check=True)
        result=subprocess.check_output([str(exe)],text=True).strip();print(f'profile={profile} force={force}: {result}')
        results.append({'profile':profile,'force':force,'result':result})
    (out/'vendor-abi-results.json').write_text(json.dumps({'scope':'Real extracted helpers with mock DMA operations, not a kernel/device test',
        'results':results,'source_sha256':{p:hashlib.sha256((args.kernel/p).read_bytes()).hexdigest() for p in paths}},indent=2)+'\n')


if __name__=='__main__':
    main()
