#!/usr/bin/env bash
# Run on a Linux filesystem with Clang/LLD 16; never invokes device tools.
set -euo pipefail
package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
build_root=${1:?Usage: build_linux.sh /absolute/new-build-directory}
case "$build_root" in /*) ;; *) echo 'Use an absolute build directory' >&2; exit 2 ;; esac
if [[ -e "$build_root" ]]; then
    echo 'Build directory must not already exist; refusing to alter an existing checkout.' >&2
    exit 2
fi
for tool in git make clang-16 ld.lld-16 llvm-ar-16 aarch64-linux-gnu-gcc arm-linux-gnueabi-gcc python3; do
    command -v "$tool" >/dev/null
done
mkdir -p -- "$build_root"
exec > >(tee "$build_root/driver.log") 2>&1
base=68473250d52537fce466ec6f10b0f67ed1e5b2dc
git init "$build_root/kernel"
git -C "$build_root/kernel" remote add origin https://github.com/duckyduckG/android_kernel_xiaomi_sdm845_419.git
git -C "$build_root/kernel" fetch --depth=1 origin "$base"
git -C "$build_root/kernel" checkout --detach FETCH_HEAD
test "$(git -C "$build_root/kernel" rev-parse HEAD)" = "$base"
cd "$package"
sha256sum -c patches/SHA256SUMS
cd "$build_root/kernel"
while read -r digest patch; do
    patch=${patch%$'\r'}
    git apply --check "$package/$patch"
    git apply "$package/$patch"
done < "$package/patches/SHA256SUMS"
export PATH=/usr/lib/llvm-16/bin:$PATH ARCH=arm64 SUBARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi- CLANG_TRIPLE=aarch64-linux-gnu-
export KBUILD_BUILD_USER=codex KBUILD_BUILD_HOST=pe13-offline KBUILD_BUILD_VERSION=1
export SOURCE_DATE_EPOCH=$(git show -s --format=%ct "$base")
export KBUILD_BUILD_TIMESTAMP=$(date -u -d "@$SOURCE_DATE_EPOCH" '+%a %b %d %T UTC %Y')
args=(O=out CC=clang-16 LD=ld.lld-16 AR=llvm-ar-16 NM=llvm-nm-16 OBJCOPY=llvm-objcopy-16 OBJDUMP=llvm-objdump-16 STRIP=llvm-strip-16)
{ clang-16 --version; ld.lld-16 --version; aarch64-linux-gnu-gcc --version; arm-linux-gnueabi-gcc --version; dpkg-query -W; } > "$build_root/toolchain.txt"
make "${args[@]}" vendor/sdm845-perf_defconfig vendor/xiaomi/sdm845-common.config vendor/xiaomi/polaris.config vendor/xiaomi/polaris-pe13.config |& tee "$build_root/config.log"
python3 "$package/scripts/check_config.py" out/.config | tee "$build_root/config-check.json"
python3 "$package/tests/run_host_checks.py" --kernel "$PWD" --cc clang-16
python3 "$package/tests/check_f2fs_layout.py" --kernel "$PWD" --cc clang-16
python3 "$package/tests/check_pe13_rotation.py" --kernel "$PWD" --cc clang-16
python3 "$package/tests/check_pe13_vendor_abi.py" --kernel "$PWD" --cc clang-16
python3 "$package/tests/check_pe13_fence_query.py" --kernel "$PWD" --cc clang-16
python3 "$package/tests/check_pe13_fence_timeline.py" --kernel "$PWD" --cc clang-16
python3 "$package/tests/check_sde_fence_completion.py" --kernel "$PWD" --cc clang-16
python3 "$package/tests/check_pe13_splash_vblank.py" --kernel "$PWD" --cc clang-16
python3 "$package/tests/check_rekernel_compat.py" --kernel "$PWD" --cc clang-16
python3 "$package/tests/check_pe13_boost_abi.py" --kernel "$PWD" --cc clang-16
mkdir "$build_root/artifacts"
if [[ ${PE13_DTB_ONLY:-0} == 1 ]]; then
    mapfile -t dtb_targets < <(find arch/arm64/boot/dts/xiaomi/polaris -maxdepth 1 -name '*.dts' ! -name '*-overlay.dts' -printf 'xiaomi/polaris/%f\n' | sed 's/\.dts$/.dtb/' | LC_ALL=C sort)
    test "${#dtb_targets[@]}" = 14
    make -j"${JOBS:-4}" "${args[@]}" "${dtb_targets[@]}" |& tee "$build_root/build.log"
    for dtb in "${dtb_targets[@]}"; do
        cp "out/arch/arm64/boot/dts/$dtb" "$build_root/artifacts/"
    done
else
    make -j"${JOBS:-4}" "${args[@]}" Image.gz-dtb |& tee "$build_root/build.log"
    test -s out/arch/arm64/boot/Image.gz-dtb
    cp out/arch/arm64/boot/Image.gz-dtb "$build_root/artifacts/pe13-419-r10-NOT-FOR-FLASHING.bin"
fi
cp out/.config "$build_root/artifacts/kernel.config"
sha256sum "$build_root/artifacts/"* > "$build_root/artifacts/SHA256SUMS"
printf '%s\n' 'Requested build targets passed; see PE13_DTB_ONLY for build scope. Not a device test.'
