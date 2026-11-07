# Experimental ReKernel integration

This directory is an untested work in progress. It is not a buildable or flashable release.

The baseline target is PixelExperience polaris kernel commit
`dce351ed301019553d148266a62fd3274f69ff22`.

`experimental-wire8.patch` is an experimental adaptation of the direct integration
source at Sakion-Team/Re-Kernel commit
`ac08296174d7fb2801c0eee1084f067a34f8a0fe`. It adds the binary netlink command
and monitored UID list behavior examined in lzghzr/APatch_kpm commit
`a931acff0d70ccae3065f4d8e4031688236da18c`, whose KPM version is 8.0.0.

This is not the original 8.0.0 KPM implementation and has not been shown to
match all of its behaviors. The integration source calls itself 8.5; version
labels must not be treated as proof of equivalence. Networking hook placement,
kernel-4.9 compatibility, concurrency, startup, security, and NoActive
interop require review and testing. Do not flash a build merely because it compiles.

Upstream: https://github.com/Sakion-Team/Re-Kernel and
https://github.com/lzghzr/APatch_kpm. Retain upstream licenses when distributing.
