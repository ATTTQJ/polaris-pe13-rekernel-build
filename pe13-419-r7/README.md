# PE13 Polaris 4.19 r7 candidate

Pinned base 68473250d52537fce466ec6f10b0f67ed1e5b2dc; apply nine patches in manifest order.

r6 restored desktop icons/screenshots and automatically initialized modem and Wi-Fi under enforcing SELinux. Actual native/compat CUSTOM cache requests succeeded. The user still reported visible scrolling stutter.

A bounded trace of the explicit Settings homepage recorded 41 late frames of 56. HWC atomic commit spans frequently took about 50 ms. A separate raw syscall trace recorded 29 real atomic ioctls with median 0.377 ms and 59 legacy object-property ioctls (56 completed with median 24.0325 ms), all returning success. Source comparison shows 4.9 dispatched vendor fence property queries to current-state callbacks, whereas 4.19 creates full atomic commits for these legacy requests.

Patch 0009 adds an optional narrowly scoped callback after DRM object-access and property-membership checks. Only the exact installed SDE output_fence on CRTCs and RETIRE_FENCE on connectors are handled; value validation, modeset locking, existing SDE fence creation/copy/error handling and DRM reference cleanup remain active. All other properties return to the normal atomic path. Full atomic frame requests are unchanged. This candidate still needs full build and device timing/visual verification.

Host tests use extracted functions and mocks. They do not prove real fence ordering or display performance. No personal logs, keys, userdata or partition backups are in this source package. No persistent device flashing is part of the build workflow.
