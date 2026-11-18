"""Compile the real rotation installer and conversion with mocked DRM allocation.

Checks the shared-property ABI and validation; not a display or kernel test.
"""
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
#include <stdlib.h>
#include <errno.h>
#define IS_ENABLED(x) (x)
#define CONFIG_FSCRYPT_LEGACY_ICE_PE13 PROFILE
#define DRM_MODE_ROTATE_0 1
#define DRM_MODE_ROTATE_90 2
#define DRM_MODE_ROTATE_180 4
#define DRM_MODE_ROTATE_270 8
#define DRM_MODE_REFLECT_X 16
#define DRM_MODE_REFLECT_Y 32
#define DRM_MODE_PROP_BITMASK 32
#define DRM_MODE_PROP_ENUM 8
#define BIT(n) (1UL << (n))
#define SDE_SSPP_TRUE_INLINE_ROT 0
#define PLANE_PROP_PE13_ROTATION 0
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define SDE_ERROR(...) ((void)0)
#define DRM_ERROR(...) ((void)0)
struct drm_property { unsigned int mask; };
struct drm_prop_enum_list { int type; const char *name; };
struct drm_device { int dummy; };
struct drm_mode_object { struct drm_property *property; uint64_t value; };
struct drm_plane { struct drm_mode_object base; struct drm_property *rotation_property; };
struct msm_property_data { uint64_t default_value; int force_dirty; };
struct msm_property_info {
    struct drm_device *dev;
    struct drm_mode_object *base;
    struct drm_property **property_array;
    struct msm_property_data *property_data;
    unsigned int property_count, install_count, install_request;
};
struct sde_plane { struct drm_plane base; unsigned long features; struct msm_property_info property_info; };
struct sde_mdss_cfg { int dummy; };
#define to_sde_plane(p) ((struct sde_plane *)(p))
static unsigned int allocations, normal_calls;
static int allocation_fail;
static struct drm_property *drm_property_create_bitmask(struct drm_device *dev,
    int flags, const char *name, const struct drm_prop_enum_list *values,
    int count, uint64_t supported) {
    if (allocation_fail) return NULL;
    struct drm_property *p = calloc(1, sizeof(*p));
    assert(p); allocations++;
    for (int i=0; i<count; ++i)
        if (supported & (1ULL << values[i].type)) p->mask |= 1U << values[i].type;
    return p;
}
static struct drm_property *drm_property_create_enum(struct drm_device *dev,
    int flags, const char *name, const struct drm_prop_enum_list *values, int count) {
    abort();
}
static void drm_object_attach_property(struct drm_mode_object *obj,
    struct drm_property *prop, uint64_t value) { obj->property=prop; obj->value=value; }
static int drm_plane_create_rotation_property(struct drm_plane *p,
    unsigned int rotation, unsigned int mask) { normal_calls++; return 0; }
'''
TEST = r'''
int main(void) {
    struct drm_device dev={0}; struct sde_mdss_cfg catalog={0};
    struct drm_property *shared[1]={0}; struct msm_property_data data[3][1]={0};
    struct sde_plane planes[3]={0};
    for (int i=0; i<3; i++) {
        planes[i].property_info=(struct msm_property_info){.dev=&dev,
            .base=&planes[i].base.base, .property_array=shared,
            .property_data=data[i], .property_count=1};
        sde_plane_rot_install_properties(&planes[i].base, &catalog);
    }
    if (PROFILE) {
        assert(allocations==1 && normal_calls==0);
        for (int i=0; i<3; i++) {
            assert(planes[i].base.base.property==shared[0]);
            assert(planes[i].base.base.value==0);
            assert(planes[i].base.rotation_property==NULL);
            assert(planes[i].property_info.install_count==1);
        }
        assert(shared[0]->mask==49);
        struct drm_property *other[1]={0};
        planes[0].property_info.property_array=other;
        sde_plane_rot_install_properties(&planes[0].base,&catalog);
        assert(other[0] && other[0]!=shared[0]);
        free(other[0]); free(shared[0]); shared[0]=NULL;
        planes[0].property_info.property_array=shared;
        planes[0].base.base.property=NULL;
        allocation_fail=1;
        sde_plane_rot_install_properties(&planes[0].base,&catalog);
        assert(!shared[0] && !planes[0].base.base.property);
        allocation_fail=0;
    } else assert(normal_calls==3 && allocations==0);
    unsigned int before=normal_calls;
    planes[0].features=BIT(SDE_SSPP_TRUE_INLINE_ROT);
    sde_plane_rot_install_properties(&planes[0].base,&catalog);
    assert(normal_calls==before+1); /* unsupported hardware keeps standard ABI */
    uint32_t rotation;
    for (uint64_t value=0; value<64; ++value) {
        rotation=0xdeadbeef;
        int ret=sde_plane_pe13_rotation(value,&rotation);
        if (value & 14) assert(ret==-EINVAL && rotation==0xdeadbeef);
        else assert(ret==0 && rotation==(value|1));
    }
    for (int bit=6; bit<64; ++bit) {
        rotation=0xdeadbeef;
        assert(sde_plane_pe13_rotation((1ULL<<bit)|1,&rotation)==-EINVAL);
        assert(rotation==0xdeadbeef);
    }
    puts("PASS shared rotation scope, legacy zero/reflections, invalid bits, standard profile and inline-rotator path");
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kernel', type=Path, default=ROOT/'kernel-4.19')
    parser.add_argument('--cc', nargs='+', default=[str(ROOT/'.tools/python/ziglang/zig.exe'), 'cc'])
    args = parser.parse_args()
    paths = ['techpack/display/msm/sde/sde_plane.c', 'techpack/display/msm/msm_prop.c']
    plane, prop = [(args.kernel/p).read_text() for p in paths]
    # Verify the tested conversion is actually used by the property setter.
    setter = function(plane, 'sde_plane_atomic_set_property')
    assert 'ret = sde_plane_pe13_rotation(val, &pe13_rotation);' in setter
    assert 'state->rotation = pe13_rotation;' in setter
    assert 'pstate->base.rotation = DRM_MODE_ROTATE_0;' in function(plane, 'sde_plane_reset')
    source = MOCK + function(prop, 'msm_property_install_enum')
    source += function(plane, 'sde_plane_pe13_rotation')
    source += function(plane, 'sde_plane_rot_install_properties') + TEST
    out = ROOT/'out/host-checks'
    out.mkdir(parents=True, exist_ok=True)
    file = out/'pe13_rotation.c'
    file.write_text(source, newline='\n')
    results = []
    for profile in [0, 1]:
        exe = out/('pe13_rotation'+str(profile)+('.exe' if sys.platform=='win32' else ''))
        subprocess.run(args.cc+['-std=gnu11','-O1','-Wall','-Wextra','-Werror',
            '-Wno-unused-function','-Wno-unused-parameter','-Wno-sign-compare',
            '-DPROFILE='+str(profile),str(file),'-o',str(exe)],check=True)
        result = subprocess.check_output([str(exe)],text=True).strip()
        print(f'profile={profile}: {result}')
        results.append({'profile':profile,'result':result})
    record = {'scope':'Real extracted functions with mocked DRM allocation; not a display or kernel test.',
        'results':results, 'source_sha256':{p:hashlib.sha256((args.kernel/p).read_bytes()).hexdigest() for p in paths}}
    (out/'rotation-results.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__ == '__main__':
    main()
