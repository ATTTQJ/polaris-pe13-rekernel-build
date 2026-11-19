"""Compile the real PE13 dither selector against mocked DRM and display state."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from run_host_checks import function


ROOT = Path(__file__).resolve().parents[1]
SELECTOR = 'techpack/display/msm/msm_atomic.c'
DISPATCH = 'drivers/gpu/drm/drm_mode_object.c'

MOCK = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#define CONFIG_DRM_MSM_SDE HAS_SDE
#define IS_ENABLED(value) (value)
#define READ_ONCE(value) (value)
#define DRM_MODE_OBJECT_CONNECTOR 1
#define DRM_MODE_CONNECTOR_DSI 2
#define connector_status_connected 1
#define DRM_MODE_PROP_BLOB 16
#define DRM_MODE_DPMS_ON 0
#define SDE_MODE_DPMS_ON 0
#define CONNECTOR_PROP_PP_DITHER 0
#define CONNECTOR_PROP_LP 1
struct drm_mode_object { int type; };
struct drm_property { unsigned flags; };
struct drm_device { void *dev_private; };
struct drm_crtc { unsigned mask; };
struct drm_crtc_state { bool enable, active, modeset; };
struct drm_connector_state { struct drm_crtc *crtc; uint64_t values[2]; };
struct drm_connector { struct drm_mode_object base; int connector_type; int status; };
struct drm_atomic_state {
    struct drm_device *dev;
    struct drm_connector_state *connector;
    struct drm_crtc_state *crtc;
};
struct dsi_panel { bool panel_initialized; };
struct dsi_display { struct dsi_panel *panel; bool is_cont_splash_enabled, poms_pending; };
struct sde_connector {
    struct drm_connector base;
    struct dsi_display *display;
    int lock, dpms_mode, last_panel_power_mode;
    void *blob_dither;
    bool allow_bl_update, panel_dead, bl_scale_dirty;
};
struct msm_drm_private {
    bool shutdown_in_progress;
    struct drm_property *conn_property[1];
    struct { int lock; } pending_crtcs_event;
    unsigned pending_crtcs, pending_planes;
};
#define obj_to_connector(obj) ((struct drm_connector *)(obj))
#define to_sde_connector(connector) ((struct sde_connector *)(connector))
#define sde_connector_get_property(state, idx) ((state)->values[(idx)])
static struct drm_connector_state *drm_atomic_get_old_connector_state(
        struct drm_atomic_state *state, struct drm_connector *connector) {
    (void)connector;
    return state->connector;
}
static struct drm_crtc_state *drm_atomic_get_old_crtc_state(
        struct drm_atomic_state *state, struct drm_crtc *crtc) {
    assert(crtc == state->connector->crtc);
    return state->crtc;
}
static bool drm_atomic_crtc_needs_modeset(struct drm_crtc_state *state) { return state->modeset; }
static unsigned drm_crtc_mask(struct drm_crtc *crtc) { return crtc->mask; }
static void spin_lock(int *lock) { assert((*lock)++ == 0); }
static void spin_unlock(int *lock) { assert((*lock)-- == 1); }
static bool mutex_trylock(int *lock) { if (*lock) return false; ++*lock; return true; }
static void mutex_unlock(int *lock) { assert((*lock)-- == 1); }
'''

TEST = r'''
int main(void) {
    struct drm_property dither = {DRM_MODE_PROP_BLOB}, other = {DRM_MODE_PROP_BLOB};
    struct msm_drm_private priv = {.conn_property = {&dither}};
    struct drm_device device = {.dev_private = &priv};
    struct drm_crtc crtc = {.mask = 2};
    struct drm_crtc_state crtc_state = {.enable = true, .active = true};
    struct drm_connector_state connector_state = {.crtc = &crtc};
    struct drm_atomic_state state = {&device, &connector_state, &crtc_state};
    struct dsi_panel panel = {true};
    struct dsi_display display = {.panel = &panel};
    struct sde_connector connector = {
        .base = {{DRM_MODE_OBJECT_CONNECTOR}, DRM_MODE_CONNECTOR_DSI, connector_status_connected},
        .display = &display, .blob_dither = &dither, .allow_bl_update = true,
    };
    struct drm_mode_object *obj = &connector.base.base;
#define NOOP() msm_atomic_pe13_legacy_noop(&state, obj, &dither, 0)
#define REJECT(field, value, original) do { field = value; assert(!NOOP()); field = original; } while (0)
    assert(NOOP() == HAS_SDE);
    assert(!msm_atomic_pe13_legacy_noop(&state, obj, &other, 0));
    assert(!msm_atomic_pe13_legacy_noop(&state, obj, &dither, 7));
    REJECT(device.dev_private, NULL, &priv);
    REJECT(obj->type, 42, DRM_MODE_OBJECT_CONNECTOR);
    REJECT(connector.base.status, 0, connector_status_connected);
    REJECT(connector.base.connector_type, 42, DRM_MODE_CONNECTOR_DSI);
    REJECT(dither.flags, 0, DRM_MODE_PROP_BLOB);
    REJECT(connector_state.values[CONNECTOR_PROP_PP_DITHER], 7, 0);
    REJECT(connector_state.values[CONNECTOR_PROP_LP], 2, 0);
    REJECT(state.connector, NULL, &connector_state);
    REJECT(connector_state.crtc, NULL, &crtc);
    REJECT(state.crtc, NULL, &crtc_state);
    REJECT(crtc_state.active, false, true);
    REJECT(crtc_state.enable, false, true);
    REJECT(crtc_state.modeset, true, false);
    REJECT(priv.pending_crtcs, crtc.mask, 0);
    REJECT(priv.pending_planes, 1, 0);
    REJECT(priv.shutdown_in_progress, true, false);
    REJECT(connector.display, NULL, &display);
    REJECT(display.panel, NULL, &panel);
    REJECT(connector.lock, 1, 0);
    REJECT(connector.blob_dither, NULL, &dither);
    REJECT(connector.dpms_mode, 3, 0);
    REJECT(connector.last_panel_power_mode, 3, 0);
    REJECT(connector.allow_bl_update, false, true);
    REJECT(connector.panel_dead, true, false);
    REJECT(connector.bl_scale_dirty, true, false);
    REJECT(panel.panel_initialized, false, true);
    REJECT(display.is_cont_splash_enabled, true, false);
    REJECT(display.poms_pending, true, false);
    assert(NOOP() == HAS_SDE && !connector.lock && !priv.pending_crtcs_event.lock);
    puts("PASS exact zero dither update, modeset and in-flight guards, panel transitions, and lock balance");
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--cc', nargs='+', required=True)
    args = parser.parse_args()
    paths = [SELECTOR, DISPATCH, 'techpack/display/msm/msm_drv.c', 'include/drm/drm_mode_config.h']
    texts = {path: (args.kernel / path).read_text(encoding='utf-8') for path in paths}
    code = function(texts[SELECTOR], 'msm_atomic_pe13_legacy_noop')
    dispatch = function(texts[DISPATCH], 'set_property_atomic')
    assert (dispatch.index('drm_atomic_set_property(') < dispatch.index('if (ret)')
            < dispatch.index('IS_ENABLED(CONFIG_FSCRYPT_LEGACY_ICE_PE13)')
            < dispatch.index('->pe13_legacy_noop(') < dispatch.index('ret = drm_atomic_commit('))
    assert 'drm_modeset_drop_locks(&ctx);' in dispatch and 'drm_atomic_state_put(state);' in dispatch
    assert '.pe13_legacy_noop = msm_atomic_pe13_legacy_noop,' in texts[paths[2]]
    assert '(*pe13_legacy_noop)' in texts[paths[3]]
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / 'check.c'
        executable = Path(folder) / 'check'
        source.write_text(MOCK + code + TEST, encoding='utf-8')
        results = []
        for supported in (0, 1):
            subprocess.run(args.cc + ['-std=gnu11', '-Wall', '-Wextra', '-Werror', f'-DHAS_SDE={supported}',
                                      str(source), '-o', str(executable)], check=True)
            result = subprocess.check_output([str(executable)], text=True).strip()
            print(result)
            results.append(result)
    output = ROOT / 'out' / 'host-checks'
    output.mkdir(parents=True, exist_ok=True)
    proof = {'results': results, 'source_sha256': {p: hashlib.sha256(texts[p].encode()).hexdigest() for p in paths}}
    (output / 'dither-noop-results.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
