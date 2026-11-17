# PE13 Polaris r3 thermal device-tree candidate

Pinned source: 68473250d52537fce466ec6f10b0f67ed1e5b2dc.
Apply patches in patches/SHA256SUMS order. Patch 0003 restores the legacy
usbc-therm-monitor and fps-therm-monitor zones using the real PM8998 ADC
AMUX_THM3_PU2 (0x4f), retaining all existing zones and the old trip values.
The thermal framework in this source attaches a sensor to all matching zones.

This CI run builds all 14 Polaris DTBs only (PE13_DTB_ONLY=1). It does not
recompile kernel executable code. The candidate reuses the previously compiled
r2 Image, whose SHA256 (with original DTBs) is
c4a0d4e5fdc98914b0ed2943216896f21b2d65d95e8d0a4d0e0b61881999ec96.
DTB artifacts alone are not boot images. Device compatibility is unverified.

Separate GPU runtime finding: the supplied vendor A630 SQE 1.87 lacks the
WHERE_AM_I security mechanism used by this kernel. A volatile ramdisk override
using pinned linux-firmware SQE 2.07 removed the observed GPU faults. It did
not complete Android boot due to missing legacy thermal sensor names.
No firmware or private device logs are included in this public package.
