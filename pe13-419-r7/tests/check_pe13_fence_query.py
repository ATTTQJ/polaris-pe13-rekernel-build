"""Host-check the real narrow legacy fence callback; no real DRM/fence hardware."""
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
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <errno.h>
#define IS_ENABLED(c) (c)
#define CONFIG_FSCRYPT_LEGACY_ICE_PE13 PROFILE
#define ENOIOCTLCMD 515
#define DRM_MODE_OBJECT_CRTC 1
#define DRM_MODE_OBJECT_CONNECTOR 2
#define CRTC_PROP_OUTPUT_FENCE 0
#define CONNECTOR_PROP_RETIRE_FENCE 0
struct drm_mode_object { unsigned type; };
struct drm_device { void *dev_private; };
struct drm_property { struct drm_device *dev; };
struct drm_crtc;
struct drm_connector;
struct drm_crtc_funcs { int (*atomic_set_property)(struct drm_crtc *,void *,struct drm_property *,uint64_t); };
struct drm_connector_funcs { int (*atomic_set_property)(struct drm_connector *,void *,struct drm_property *,uint64_t); };
struct drm_crtc { struct drm_mode_object base; void *state; const struct drm_crtc_funcs *funcs; };
struct drm_connector { struct drm_mode_object base; void *state; const struct drm_connector_funcs *funcs; };
struct msm_drm_private { struct drm_property *crtc_property[1], *conn_property[1]; };
#define obj_to_crtc(o) ((struct drm_crtc *)(o))
#define obj_to_connector(o) ((struct drm_connector *)(o))
static unsigned valid_gets,valid_puts,locks,unlocks,crtc_calls,conn_calls;
static bool locked,valid=true;
static int setter_result;
static uint64_t received;
static void *expected_state;
static struct drm_mode_object reference;
static bool drm_property_change_valid_get(struct drm_property *p,uint64_t v,struct drm_mode_object **ref) {
    (void)p;(void)v;valid_gets++;if(valid)*ref=&reference;return valid;
}
static void drm_property_change_valid_put(struct drm_property *p,struct drm_mode_object *ref) {
    (void)p;assert(locked && ref==&reference);valid_puts++;
}
static void drm_modeset_lock_all(struct drm_device *d) { (void)d;assert(!locked);locked=true;locks++; }
static void drm_modeset_unlock_all(struct drm_device *d) { (void)d;assert(locked);locked=false;unlocks++; }
static int crtc_set(struct drm_crtc *c,void *s,struct drm_property *p,uint64_t v) {
    (void)c;(void)p;assert(locked && s==expected_state);crtc_calls++;received=v;return setter_result;
}
static int conn_set(struct drm_connector *c,void *s,struct drm_property *p,uint64_t v) {
    (void)c;(void)p;assert(locked && s==expected_state);conn_calls++;received=v;return setter_result;
}
'''
TEST = r'''
int main(void) {
    struct msm_drm_private priv={0};
    struct drm_device dev={&priv};
    struct drm_property output={&dev},retire={&dev},other={&dev};
    priv.crtc_property[0]=&output;priv.conn_property[0]=&retire;
    const struct drm_crtc_funcs cf={crtc_set};
    const struct drm_connector_funcs nf={conn_set};
    int current_state;
    expected_state=&current_state;
    struct drm_crtc crtc={{DRM_MODE_OBJECT_CRTC},expected_state,&cf};
    struct drm_connector conn={{DRM_MODE_OBJECT_CONNECTOR},expected_state,&nf};
    struct drm_mode_object plane={3};
    assert(msm_atomic_pe13_legacy_fence(&crtc.base,&other,12)==-ENOIOCTLCMD);
    assert(msm_atomic_pe13_legacy_fence(&conn.base,&output,12)==-ENOIOCTLCMD);
    assert(msm_atomic_pe13_legacy_fence(&plane,&output,12)==-ENOIOCTLCMD);
    assert(valid_gets==0 && locks==0 && crtc_calls==0 && conn_calls==0);
    if(!PROFILE) {
        assert(msm_atomic_pe13_legacy_fence(&crtc.base,&output,12)==-ENOIOCTLCMD);
        assert(msm_atomic_pe13_legacy_fence(&conn.base,&retire,12)==-ENOIOCTLCMD);
        assert(valid_gets==0 && locks==0);
    } else {
        uint64_t pointer=UINT64_C(0x123456789abcdef0);
        assert(msm_atomic_pe13_legacy_fence(&crtc.base,&output,pointer)==0);
        assert(received==pointer && crtc_calls==1 && conn_calls==0);
        setter_result=-EFAULT;
        assert(msm_atomic_pe13_legacy_fence(&conn.base,&retire,pointer)==-EFAULT);
        assert(received==pointer && conn_calls==1 && locks==2 && unlocks==2 && valid_puts==2 && !locked);
        valid=false;
        assert(msm_atomic_pe13_legacy_fence(&crtc.base,&output,pointer)==-EINVAL);
        assert(valid_gets==3 && valid_puts==2 && locks==2 && crtc_calls==1);
        dev.dev_private=NULL;
        assert(msm_atomic_pe13_legacy_fence(&crtc.base,&output,pointer)==-ENOIOCTLCMD);
    }
    puts("PASS PE13 profile isolation, exact property/object identity, current-state routing, validation, lock/ref balance and setter error propagation");
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kernel', type=Path, default=ROOT/'kernel-4.19')
    parser.add_argument('--cc', nargs='+', default=[str(ROOT/'.tools/python/ziglang/zig.exe'), 'cc'])
    args = parser.parse_args()
    paths = ['techpack/display/msm/msm_atomic.c', 'techpack/display/msm/msm_drv.c',
             'techpack/display/msm/msm_drv.h', 'include/drm/drm_mode_config.h',
             'drivers/gpu/drm/drm_mode_object.c']
    texts = [(args.kernel/p).read_text() for p in paths]
    helper = function(texts[0], 'msm_atomic_pe13_legacy_fence')
    assert 'drm_atomic_commit(' not in helper
    assert '.pe13_legacy_fence = msm_atomic_pe13_legacy_fence,' in texts[1]
    core = function(texts[4], 'drm_mode_obj_set_property_ioctl')
    assert core.index('drm_mode_object_find(') < core.index('drm_mode_obj_find_prop_id(') < core.index('pe13_legacy_fence(') < core.index('set_property_atomic(')
    assert 'if (ret != -ENOIOCTLCMD)' in core
    out = ROOT/'out/host-checks'
    out.mkdir(exist_ok=True)
    source = out/'pe13_fence_query.c'
    source.write_text(MOCK+helper+TEST, newline='\n')
    results = []
    for profile in [0, 1]:
        exe = out/(f'pe13_fence_query{profile}'+('.exe' if sys.platform=='win32' else ''))
        subprocess.run(args.cc+['-std=gnu11', '-O1', '-Wall', '-Wextra', '-Werror',
                               f'-DPROFILE={profile}', str(source), '-o', str(exe)], check=True)
        value = subprocess.check_output([str(exe)], text=True).strip()
        print(value)
        results.append({'profile': profile, 'result': value})
    (out/'fence-query-results.json').write_text(json.dumps({
        'scope': 'Real extracted callback with DRM mocks; not a live fence or display test',
        'results': results,
        'source_sha256': {p: hashlib.sha256((args.kernel/p).read_bytes()).hexdigest() for p in paths}}, indent=2)+'\n')


if __name__ == '__main__':
    main()
