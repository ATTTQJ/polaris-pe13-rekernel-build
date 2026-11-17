# PE13 polaris 4.19 r10 candidate

Pinned source: duckyduckG/android_kernel_xiaomi_sdm845_419 68473250d52537fce466ec6f10b0f67ed1e5b2dc.

r9 boots but the legacy HWC initial drmWaitVBlank request fails with EINVAL. Bounded request tracing confirms a valid CRTC-0 RELATIVE|EVENT request, sequence 1. Reinitializing HWC reproduces the failure. The driver resets every CRTC vblank state before adopting an already active continuous-splash display, but does not balance that reset during adoption. The old vendor registers VSync before the first ordinary modeset.

r10 retains the preceding thirteen patches, ReKernel and boost compatibility, and calls drm_crtc_vblank_on only after successful adoption of an active/enabled splash CRTC under the PE13 compatibility configuration. Other CRTCs and configuration-disabled behavior remain unchanged. No ioctl validation, authentication, permissions, clock or refresh-mode limits are relaxed.

A host regression runs real DRM reset/get/on functions around the actual compatibility helper, with hardware enable/locks mocked. It reproduces the initial EINVAL and checks that the adopted CRTC can register while the other CRTC remains blocked. Fourteen patches and ten source-check scripts are hash-bound. These checks are not proof of real interrupts, startup or smoothness; full build and device acceptance remain necessary. Raw output is not a flashable boot image. Use the verified original ramdisk and SQE 2.07 override for temporary device testing. No private device data is included. ReKernel provenance/license remain as documented in r8/r9 and licenses/ReKernel-COPYING.
