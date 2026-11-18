"""Run the real SDE fence completion predicate across advance and wrap cases."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from run_host_checks import function

ROOT = Path(__file__).resolve().parents[1]
MOCK = r'''
#undef NDEBUG
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef int32_t s32;
struct sde_fence_context { uint32_t done_count; };
struct dma_fence { uint32_t seqno; };
struct sde_fence { struct dma_fence base; struct sde_fence_context *ctx; };
#define to_sde_fence(x) ((struct sde_fence *)(x))
#define SDE_DEBUG(...) ((void)0)
'''
TEST = r'''
int main(void) {
    struct sde_fence_context ctx={0};
    struct sde_fence f={{0},&ctx};
    const uint32_t done[]={0,1,2,1234,0x7ffffffe,0x80000000,0xfffffffe,0xffffffff};
    for (unsigned i=0;i<sizeof(done)/sizeof(done[0]);i++) {
        ctx.done_count=done[i];
        for (int delta=-4;delta<=4;delta++) {
            f.base.seqno=done[i]+(uint32_t)delta;
            assert(sde_fence_signaled(&f.base)==(delta<=0));
        }
    }
    puts("PASS SDE fence exact, older, future and uint32 wrap completion");
}
'''


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--kernel',type=Path,default=ROOT/'kernel-4.19')
    p.add_argument('--cc',nargs='+',default=[str(ROOT/'.tools/python/ziglang/zig.exe'),'cc'])
    args=p.parse_args()
    name='techpack/display/msm/sde/sde_fence.c'
    data=(args.kernel/name).read_bytes().replace(b'\r\n',b'\n')
    body=function(data.decode(),'sde_fence_signaled')
    out=ROOT/'out/host-checks';out.mkdir(exist_ok=True)
    source=out/'sde_fence_completion.c';source.write_text(MOCK+body+TEST,newline='\n')
    exe=out/('sde_fence_completion'+('.exe' if sys.platform=='win32' else ''))
    subprocess.run(args.cc+['-std=gnu11','-O1','-Wall','-Wextra','-Werror',str(source),'-o',str(exe)],check=True)
    result=subprocess.check_output([str(exe)],text=True).strip()
    (out/'fence-completion-results.json').write_text(json.dumps({'scope':'Real predicate with mocked fence/context; not runtime wakeup or smoothness proof',
        'result':result,'source_sha256':{name:hashlib.sha256(data).hexdigest()}},indent=2)+'\n')
    print(result)


if __name__=='__main__':
    main()
