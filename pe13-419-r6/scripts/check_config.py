"""Reject a build whose effective config drops required compatibility settings."""
import json
from pathlib import Path
import sys

REQUIRED = {
    "CONFIG_MACH_XIAOMI_D5X": "y",
    "CONFIG_F2FS_FS": "y",
    "CONFIG_F2FS_LEGACY_EXTRA_ATTR_PE13": "y",
    "CONFIG_F2FS_FS_COMPRESSION": "n",
    "CONFIG_FS_ENCRYPTION": "y",
    "CONFIG_FS_ENCRYPTION_INLINE_CRYPT": "y",
    "CONFIG_BLK_INLINE_ENCRYPTION": "y",
    "CONFIG_BLK_INLINE_ENCRYPTION_FALLBACK": "n",
    "CONFIG_ENABLE_LEGACY_PFK": "y",
    "CONFIG_FSCRYPT_LEGACY_ICE_PE13": "y",
    "CONFIG_QTI_CRYPTO_LEGACY_SCM": "y",
    "CONFIG_QTI_CRYPTO_TZ": "y",
    "CONFIG_SCSI_UFS_CRYPTO_QTI": "y",
    "CONFIG_ANDROID_BINDER_IPC": "y",
    "CONFIG_ANDROID_BINDER_DEVICES": '"binder,hwbinder,vndbinder"',
    "CONFIG_ASHMEM": "y",
    "CONFIG_ION_LEGACY": "y",
    "CONFIG_ION_FORCE_DMA_SYNC": "y",
    "CONFIG_SECURITY_SELINUX": "y",
    "CONFIG_DM_VERITY": "y",
    "CONFIG_SECURITY_PERF_EVENTS_RESTRICT": "y",
}


def check(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            values[line[2:-11]] = "n"
    mismatches = {k: {"required": v, "actual": values.get(k, "absent")}
                  for k, v in REQUIRED.items() if values.get(k) != v}
    print(json.dumps({"effective_config": str(path), "mismatches": mismatches}, indent=2))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    check(sys.argv[1])
