"""Extract real offset helpers and distinguish post-commit from atomic queries."""
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
#define IS_ENABLED(c) (c)
#define CONFIG_FSCRYPT_LEGACY_ICE_PE13 PROFILE
#define CRTC_PROP_OUTPUT_FENCE_OFFSET 0
struct drm_crtc_state { unsigned offset; };
struct drm_crtc { struct drm_crtc_state *state; };
struct drm_connector_state { int unused; };
struct drm_connector { struct drm_connector_state *state; };
#define sde_crtc_state drm_crtc_state
#define to_sde_crtc_state(x) ((struct drm_crtc_state *)(x))
#define sde_crtc_get_property(s,p) ((s)->offset)
'''
TEST = r'''
int main(void) {
    struct drm_crtc_state current={0}, next={0};
    struct drm_crtc crtc={&current};
    struct drm_connector_state cs={0}, ns={0};
    struct drm_connector conn={&cs};
    assert(_sde_connector_retire_fence_offset(&conn,&ns)==1);
    assert(_sde_connector_retire_fence_offset(&conn,&cs)==(PROFILE ? 0 : 1));
    for(unsigned n=0;n<=1;n++) {
        current.offset=next.offset=n;
        assert(_sde_crtc_output_fence_offset(&crtc,&next,true)==n+2);
        assert(_sde_crtc_output_fence_offset(&crtc,&next,false)==n+1);
        assert(_sde_crtc_output_fence_offset(&crtc,&current,true)==n+(PROFILE ? 1 : 2));
        assert(_sde_crtc_output_fence_offset(&crtc,&current,false)==(PROFILE ? 0 : n+1));
    }
    puts("PASS legacy post-commit release/retire timelines and unchanged atomic-list offsets");
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kernel', type=Path, default=ROOT/'kernel-4.19')
    parser.add_argument('--cc', nargs='+', default=[str(ROOT/'.tools/python/ziglang/zig.exe'), 'cc'])
    args = parser.parse_args()
    names = ['techpack/display/msm/sde/sde_crtc.c', 'techpack/display/msm/sde/sde_connector.c']
    texts = [(args.kernel/name).read_text() for name in names]
    helpers = function(texts[0], '_sde_crtc_output_fence_offset')+function(texts[1], '_sde_connector_retire_fence_offset')
    assert '_sde_crtc_output_fence_offset(crtc, state, is_vid)' in function(texts[0], '_sde_crtc_get_output_fence')
    assert '_sde_connector_retire_fence_offset(connector, state)' in function(texts[1], 'sde_connector_atomic_set_property')
    out = ROOT/'out/host-checks'; out.mkdir(exist_ok=True)
    source = out/'pe13_fence_timeline.c'; source.write_text(MOCK+helpers+TEST, newline='\n')
    results = []
    for profile in [0, 1]:
        exe = out/(f'pe13_fence_timeline{profile}'+('.exe' if sys.platform=='win32' else ''))
        subprocess.run(args.cc+['-std=gnu11', '-O1', '-Wall', '-Wextra', '-Werror', f'-DPROFILE={profile}', str(source), '-o', str(exe)],check=True)
        result = subprocess.check_output([str(exe)], text=True).strip()
        print(result); results.append({'profile': profile, 'result': result})
    (out/'fence-timeline-results.json').write_text(json.dumps({'scope':'Extracted offset calculations with mocked DRM state; not hardware fence signaling proof', 'results':results,
        'source_sha256':{name:hashlib.sha256((args.kernel/name).read_bytes()).hexdigest() for name in names}},indent=2)+'\n')


if __name__ == '__main__':
    main()
