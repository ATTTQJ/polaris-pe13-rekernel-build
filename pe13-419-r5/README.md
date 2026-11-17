# PE13 Polaris 4.19 r5 compatibility candidate

Pinned upstream 68473250d52537fce466ec6f10b0f67ed1e5b2dc. Full kernel build, not a flashable boot image.

r4 reached an unlocked Android session and restored physical display output, but the device test FAILED usability: missing launcher icons, jank, screenshot CPU-lock failure, Wi-Fi driver start failure and Bluetooth SoC init failure. It was booted temporarily and returned to the original working 4.9 boot partition. Android boot completion is not a success criterion.

r5 adds two independently scoped candidates:

- Legacy Qualcomm ION cache ioctls with native/compat layouts, fd ownership/range validation and real full-buffer DMA cache operations. The PE13 profile enables ION_FORCE_DMA_SYNC to maintain backing SG addresses even without attachments. No user VA is dereferenced and errors are preserved.
- Old GENI UART clock ioctl numbers are translated only for the serial driver msm_geni_serial_hs in the PE13 profile, before generic PTY handling. PTYs, other UARTs and modern command numbers are unchanged.

Host tests check selected real helper control flow using mock DMA callbacks; they cannot prove cache coherence or radio operation. Wi-Fi and low frame rate remain unresolved, and r5 has not been tested on a device. This is not a daily-use kernel and does not contain the original ReKernel/V2 feature ports. Requires the separately tested SQE2.07 volatile override. No private device logs, copied vendor binaries or firmware are published here.
