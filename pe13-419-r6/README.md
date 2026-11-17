# PE13 Polaris 4.19 r6 candidate

Pinned kernel base: 68473250d52537fce466ec6f10b0f67ed1e5b2dc.
Eight patches apply in patches/SHA256SUMS order.

r5 booted, and the user confirmed Magisk, Bluetooth and camera operation, but desktop icons, performance, Wi-Fi and modem initially failed.
Actual screencap tracing observed rejected ION_IOC_CUSTOM 0xc0104906 wrapping INV 0xc0184d01 with positive legacy handle and unused fd zero. Patch 0007 adds bounded native/compat custom dispatch and legacy handle priority, using owned dma-buf cache operations without dereferencing the supplied virtual address.

The PE13 vendor policy assigns sysfs labels to original subsystem instance paths. Different 4.19 probe order gave every name attribute the generic sysfs type. Temporarily restoring the existing sysfs_ssr labels and restarting peripheral services restored modem ONLINE and baseband; the user confirmed modem and Wi-Fi recovery while SELinux remained enforcing. Patch 0008 preserves those original instance numbers, reserves them from unknown subsystems, and keeps existing access rules.

Host checks use real extracted helpers with mocked DMA and allocator operations. They do not prove screen correctness or modem functionality. Full build and a new temporary device boot remain required. No data, keys, firmware partition or vendor partition changes are part of this source package.
