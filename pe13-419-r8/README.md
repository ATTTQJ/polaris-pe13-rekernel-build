# PE13 polaris 4.19 r8 candidate

Pinned kernel: duckyduckG/android_kernel_xiaomi_sdm845_419 at 68473250d52537fce466ec6f10b0f67ed1e5b2dc.

r6 restored legacy ION screenshots/icons and automatic modem/WLAN startup but failed scrolling acceptance. r7 avoided extra frame commits for legacy fence queries, but its runtime test stalled on the boot animation. r8 distinguishes legacy post-commit fence queries from atomic-list pre-commit queries, preserving normal atomic offsets. This is a candidate, not a proven fix.

At the user's request, r8 includes Re:Kernel Binder, signal and TCP reporting with the existing wire8 commands and monitored UID behavior. Source derives from Sakion-Team/Re-Kernel ac08296174d7fb2801c0eee1084f067a34f8a0fe plus the repository's existing integration/experimental-wire8.patch. GPL-2.0 license is retained in licenses/ReKernel-COPYING. The port adds a CAP_NET_ADMIN command gate and supports the existing 4.19 cgroup freezer; no full V2 or KPM 8.0.0 behavioral-equivalence claim is made.

CAF CPU_BOOST, MSM_PERFORMANCE, SCHED_TUNE and SCHED_WALT are present and enabled. PE13 vendor init still writes the 4.9 cpu_boost module parameter paths, while this 4.19 provides modern CPU sysfs nodes. A scoped compatibility patch exposes the legacy parameters using the same boost state/parser, preserving existing policy and normal permissions.

Twelve ordered patches and eight host source checks are bound by hashes. Host mocks do not prove live fences, power behavior or app interoperability. A full Linux build, artifact checks and real-device acceptance remain necessary. Raw kernel output is not a flashable boot image. Device tests require a correctly packed ramdisk SQE 2.07 override. No private device logs or screenshots are included.
