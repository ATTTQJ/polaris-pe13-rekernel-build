# PE13 polaris 4.19 r9 candidate

Pinned source: duckyduckG/android_kernel_xiaomi_sdm845_419 68473250d52537fce466ec6f10b0f67ed1e5b2dc.

r8 boots with icons and recognized ReKernel, but scrolling acceptance failed. r9 retains all twelve compatibility patches, ReKernel and the legacy boost interface. Its new patch fixes SDE fence completion: compare the signed 32-bit sequence delta before testing <= 0. Previously the unsigned comparison was cast after it had already returned false for completed older fences. This includes wraparound within the standard half-range ordering contract.

The new host regression runs the actual driver predicate for past, exact and future sequences around uint32 wrap and the sign boundary. Thirteen ordered patches and nine host source checks are bound by hashes. This correctness fix is not proof that the remaining VSync/smoothness problem is solved. Full compilation and device acceptance are required.

Raw kernel output is not a flashable boot image. Tests require the previously verified original Magisk ramdisk and volatile SQE 2.07 override. No private device logs, screenshots or user data are included. ReKernel provenance and GPL-2.0 license remain as documented in r8 and licenses/ReKernel-COPYING.
