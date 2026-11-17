"""Exercise real DRM reset/get/on functions around PE13 splash adoption."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
from run_host_checks import function

ROOT=Path(__file__).resolve().parents[1]
MOCK=r'''
#undef NDEBUG
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stdio.h>
#define IS_ENABLED(c) (c)
#define CONFIG_FSCRYPT_LEGACY_ICE_PE13 PROFILE
#define DRM_DEBUG_VBL(...) ((void)0)
#define spin_lock_irqsave(lock,flags) do { (void)(lock); (flags)=0; } while(0)
#define spin_unlock_irqrestore(lock,flags) do { (void)(lock); (void)(flags); } while(0)
struct atomic_count { int value; };
static inline void atomic_inc(struct atomic_count *p) { ++p->value; }
static inline void atomic_dec(struct atomic_count *p) { --p->value; }
static inline int atomic_add_return(int n,struct atomic_count *p) { return p->value+=n; }
static inline int atomic_read(struct atomic_count *p) { return p->value; }
static inline bool WARN_ON(bool condition) { return condition; }
static inline bool list_empty(int *head) { (void)head; return true; }
struct drm_vblank_crtc { bool enabled; unsigned inmodeset; struct atomic_count refcount; };
struct drm_device { unsigned num_crtcs; struct drm_vblank_crtc *vblank; int vbl_lock,vblank_event_list; };
struct drm_crtc_state { bool active,enable; };
struct drm_crtc { struct drm_device *dev; unsigned index; struct drm_crtc_state *state; };
static unsigned drm_crtc_index(struct drm_crtc *c) { return c->index; }
static int enable_calls,timestamp_calls;
static int drm_vblank_offdelay=5000;
static int drm_vblank_enable(struct drm_device *dev,unsigned pipe) {
    enable_calls++; dev->vblank[pipe].enabled=true; return 0;
}
static void drm_reset_vblank_timestamp(struct drm_device *dev,unsigned pipe) {
    (void)dev; (void)pipe; timestamp_calls++;
}
#define EXPORT_SYMBOL(x)
'''
TEST=r'''
int main(void) {
    struct drm_vblank_crtc vb[2]={0};
    struct drm_device dev={.num_crtcs=2,.vblank=vb};
    struct drm_crtc_state active={true,true},inactive={false,true},off={true,false};
    struct drm_crtc primary={&dev,0,&active},other={&dev,1,&inactive};
    drm_crtc_vblank_reset(&primary); drm_crtc_vblank_reset(&other);
    assert(drm_vblank_get(&dev,0)==-EINVAL && vb[0].refcount.value==1);
    assert(drm_vblank_get(&dev,1)==-EINVAL && vb[1].refcount.value==1);
    sde_kms_pe13_splash_vblank_on(NULL);
    sde_kms_pe13_splash_vblank_on(&other);
    other.state=&off; sde_kms_pe13_splash_vblank_on(&other);
    other.state=NULL; sde_kms_pe13_splash_vblank_on(&other);
    assert(timestamp_calls==0 && enable_calls==0);
    sde_kms_pe13_splash_vblank_on(&primary);
    assert(timestamp_calls==(PROFILE?1:0));
    assert(drm_vblank_get(&dev,0)==(PROFILE?0:-EINVAL));
    assert(enable_calls==(PROFILE?1:0));
    assert(vb[1].inmodeset==1 && !vb[1].enabled && vb[1].refcount.value==1);
    assert(drm_vblank_get(&dev,1)==-EINVAL);
    puts("PASS real DRM initial reset rejects registration; PE13 active splash restores only adopted CRTC");
}
'''


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--kernel',type=Path,default=ROOT/'kernel-4.19')
    p.add_argument('--cc',nargs='+',default=[str(ROOT/'.tools/python/ziglang/zig.exe'),'cc'])
    args=p.parse_args()
    files=['drivers/gpu/drm/drm_vblank.c','techpack/display/msm/sde/sde_kms.c']
    texts=[(args.kernel/name).read_text() for name in files]
    helper=function(texts[1],'sde_kms_pe13_splash_vblank_on')
    caller=function(texts[1],'sde_kms_cont_splash_config')
    pos=caller.index('sde_kms_pe13_splash_vblank_on(crtc);')
    assert caller.count('sde_kms_pe13_splash_vblank_on(crtc);')==1
    assert pos>caller.index('_sde_kms_update_planes_for_cont_splash(')
    assert 'return rc;' in caller[caller.index('_sde_kms_update_planes_for_cont_splash('):pos]
    assert 'if (!splash_display->cont_splash_enabled)' in caller and 'continue;' in caller
    core_source=re.sub(r'/\*.*?\*/','',texts[0],flags=re.S)
    core='\n'.join(function(core_source,name) for name in ['drm_vblank_get','drm_crtc_vblank_reset','drm_crtc_vblank_on'])
    out=ROOT/'out/host-checks';out.mkdir(exist_ok=True)
    source=out/'pe13_splash_vblank.c';source.write_text(MOCK+core+helper+TEST,newline='\n')
    results=[]
    for profile in [0,1]:
        exe=out/(f'pe13_splash_vblank{profile}'+('.exe' if sys.platform=='win32' else ''))
        subprocess.run(args.cc+['-std=gnu11','-O1','-Wall','-Wextra','-Werror',f'-DPROFILE={profile}',str(source),'-o',str(exe)],check=True)
        result=subprocess.check_output([str(exe)],text=True).strip();print(result)
        results.append({'profile':profile,'result':result})
    (out/'splash-vblank-results.json').write_text(json.dumps({'scope':'Real DRM software reset/get/on with mocked hardware enabling and locks; not an IRQ or boot test',
        'results':results,'source_sha256':{name:hashlib.sha256((args.kernel/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for name in files}},indent=2)+'\n')


if __name__=='__main__':
    main()
