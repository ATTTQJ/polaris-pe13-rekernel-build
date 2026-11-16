# Polaris PE13 4.19 legacy ICE candidate r1

Experimental offline build only. No boot image or device operations.

Pinned upstream: https://github.com/duckyduckG/android_kernel_xiaomi_sdm845_419.git
Commit: 68473250d52537fce466ec6f10b0f67ed1e5b2dc

Adds opt-in compatibility for v1 PRIVATE-mode F2FS data: per-file KDF, inline hardware selection without changing the legacy fstab, no blk-crypto software fallback, legacy ICE v3 SCM calls and physical keyslot reservation. Standard policies and disabled compatibility profiles retain their original control flow.

Host tests compile extracted C functions against mocks, and do not prove Linux, TrustZone, or existing-userdata compatibility. A successful kernel build is not device validation.

Run `bash scripts/build_linux.sh /absolute/new-build-directory` on Linux with Clang/LLD 16 and AArch64/ARM32 GNU cross compilers. The script records the effective config, toolchain packages, logs and SHA256. Apt packages are not immutable version-pinned, so bit-for-bit reproducibility is not yet claimed.
