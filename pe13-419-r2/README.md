# Polaris PE13 4.19 legacy ICE candidate r2

Offline candidate. r1 failed a device boot and created 36-byte F2FS extra-attribute inodes that the original 4.9 reader rejected. That later rollback failure is distinct from the still-unknown original 4.19 boot failure.

Pinned upstream: https://github.com/duckyduckG/android_kernel_xiaomi_sdm845_419.git
Commit: 68473250d52537fce466ec6f10b0f67ed1e5b2dc

Apply patches in SHA256SUMS order. r2 adds opt-in 24-byte new-inode allocation, preserves the native 24/36-byte reader, disables compression in this profile and rejects disk feature bits newer than the 4.9 reference before mount setup/recovery. The actual packed attribute layout and extracted C helpers have host regression checks with compatibility on/off.

This only addresses the demonstrated inode-layout regression. It does not establish existing-data decryption, full rollback safety, TrustZone calls, vendor compatibility, or successful boot. Early boot diagnostics are required before another device trial. No device state or backups are uploaded here.

Run bash scripts/build_linux.sh /absolute/new-build-directory on Ubuntu 24.04 with Clang/LLD 16 and the AArch64/ARM32 cross compilers. Tools are pinned to major versions, not immutable package revisions.
