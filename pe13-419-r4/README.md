# PE13 Polaris 4.19 r4 candidate

Pinned source: duckyduckG/android_kernel_xiaomi_sdm845_419 at 68473250d52537fce466ec6f10b0f67ed1e5b2dc.

Builds the full kernel with legacy ICE, rollback-compatible F2FS, real thermal sensor aliases and the legacy PE13 shared zero-default rotation property. The rotation adapter is restricted to the PE13 profile on planes without inline rotation. Unsupported transform bits remain rejected; DRM core validation and SDE hardware checks are unchanged.

The r3 device test reached Android boot completion but had a physically black screen. A read-only atomic ioctl trace showed ENOENT because the old vendor composer reused one rotation property ID across planes. Its zero value also needs translation to ROTATE_0. r4 addresses this ABI mismatch and still requires actual display testing.

Requires the separately tested SQE 2.07 temporary firmware load; no firmware or private device logs are included. This artifact is not a boot image, not ready for flashing, and does not contain the original ReKernel/V2 feature ports.

Host mocks verify selected control flow only. Full CI compilation is not a device test. Preserve userdata, keys, vendor and boot rollback image.
