"""Compile selected real kernel functions against host mocks; no device access.

These tests verify control flow/ABI construction, not the Linux kernel or TEE.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    pos = source.index(name + "(")
    start = source.rfind("\n", 0, pos) + 1
    brace = source.index("{", pos)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


COMMON = r'''
#undef NDEBUG
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>
#ifndef EOPNOTSUPP
#define EOPNOTSUPP 95
#endif
#define IS_ENABLED(x) (x)
#define CONFIG_FSCRYPT_LEGACY_ICE_PE13 PROFILE
#define CONFIG_QTI_CRYPTO_LEGACY_SCM PROFILE
#define CONFIG_BLK_INLINE_ENCRYPTION_FALLBACK 0
#define FSCRYPT_MODE_PRIVATE 127
#define FSCRYPT_POLICY_V1 0
#define FSCRYPT_POLICY_FLAGS_PAD_MASK 3
#define FSCRYPT_POLICY_FLAG_IV_INO_LBLK_32 16
#define PAGE_SIZE 4096
#define GFP_KERNEL 0
#define GFP_NOFS 0
#define S_ISREG(m) ((m)==1)
#define fscrypt_warn(...) ((void)0)
#define pr_err(...) ((void)0)
#define min(a,b) ((a)<(b)?(a):(b))
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
enum blk_crypto_mode_num { BLK_ENCRYPTION_MODE_INVALID, BLK_ENCRYPTION_MODE_AES_256_XTS };
struct policy { int version, mode; unsigned int flags; };
struct fs_type { const char *name; };
struct super_block;
struct fs_ops { bool (*inline_crypt_enabled)(struct super_block *); };
struct super_block { struct fs_type *s_type; int s_blocksize; struct fs_ops *s_cop; };
struct inode { int i_mode; struct super_block *i_sb; };
struct mode { enum blk_crypto_mode_num blk_crypto_mode; };
struct fscrypt_info { struct inode *ci_inode; struct mode *ci_mode; struct policy ci_policy; bool ci_inlinecrypt; };
struct request_queue { int *ksm; };
static bool mount_inline, hardware_ok, allocation_fail;
static int device_count=1, capability_checks;
static bool mount_test(struct super_block *s) { (void)s; return mount_inline; }
static int fscrypt_policy_contents_mode(const struct policy *p) { return p->mode; }
static unsigned int fscrypt_policy_flags(const struct policy *p) { return p->flags; }
static int fscrypt_get_num_devices(struct super_block *s) { (void)s; return device_count; }
static void *kmalloc_array(int n, size_t s, int f) { (void)f; return allocation_fail ? NULL : calloc(n,s); }
#define kfree free
static void fscrypt_get_devices(struct super_block *s, int n, struct request_queue **q) {
    static struct request_queue queue; (void)s; for(int i=0;i<n;i++) q[i]=&queue;
}
static unsigned int fscrypt_get_dun_bytes(const struct fscrypt_info *c) { (void)c; return 8; }
static bool keyslot_manager_crypto_mode_supported(int *k, int m, unsigned int d, int s, bool w) {
    (void)k; (void)m; (void)d; (void)s; (void)w; capability_checks++; return hardware_ok;
}
struct ufs_hba { unsigned int slots; };
static unsigned int ufshcd_num_keyslots(struct ufs_hba *h) { return h->slots; }
'''

SELECTION_TEST = r'''
int main(void) {
    struct fs_type ft={"f2fs"}; struct fs_ops ops={mount_test};
    struct super_block sb={&ft,4096,&ops}; struct inode ino={1,&sb};
    struct mode mode={BLK_ENCRYPTION_MODE_AES_256_XTS};
    struct fscrypt_info ci={&ino,&mode,{0,127,0},false};
    hardware_ok=true;
    assert(fscrypt_select_encryption_impl(&ci,false)==0);
    assert(ci.ci_inlinecrypt == !!PROFILE); /* Legacy fstab, no inlinecrypt. */
    ci.ci_inlinecrypt=false; hardware_ok=false;
    assert(fscrypt_select_encryption_impl(&ci,false)==(PROFILE ? -EOPNOTSUPP : 0));
    assert(!ci.ci_inlinecrypt);
    hardware_ok=true; mount_inline=true;
    assert(fscrypt_select_encryption_impl(&ci,false)==0 && ci.ci_inlinecrypt);
    ci.ci_inlinecrypt=false; ci.ci_policy.mode=1; mount_inline=false;
    assert(fscrypt_select_encryption_impl(&ci,false)==0 && !ci.ci_inlinecrypt);
    mount_inline=true;
    assert(fscrypt_select_encryption_impl(&ci,false)==0 && ci.ci_inlinecrypt);
    ci.ci_inlinecrypt=false; ci.ci_policy.mode=127;
    if(PROFILE) {
        ci.ci_policy.version=2; assert(fscrypt_select_encryption_impl(&ci,false)==-EOPNOTSUPP);
        ci.ci_policy.version=0; ft.name="ext4"; assert(fscrypt_select_encryption_impl(&ci,false)==-EOPNOTSUPP);
        ft.name="f2fs"; sb.s_blocksize=1024; assert(fscrypt_select_encryption_impl(&ci,false)==-EOPNOTSUPP);
        sb.s_blocksize=4096; assert(fscrypt_select_encryption_impl(&ci,true)==-EOPNOTSUPP);
        ci.ci_policy.flags=16; assert(fscrypt_select_encryption_impl(&ci,false)==-EOPNOTSUPP);
        ci.ci_policy.flags=0; allocation_fail=true; assert(fscrypt_select_encryption_impl(&ci,false)==-ENOMEM);
        allocation_fail=false; device_count=0; assert(fscrypt_select_encryption_impl(&ci,false)==-EINVAL);
        device_count=1; mode.blk_crypto_mode=0; assert(fscrypt_select_encryption_impl(&ci,false)==-EOPNOTSUPP);
        mode.blk_crypto_mode=1;
        for(unsigned int flags=0;flags<4;flags++) {
            ci.ci_inlinecrypt=false; ci.ci_policy.flags=flags;
            assert(fscrypt_select_encryption_impl(&ci,false)==0 && ci.ci_inlinecrypt);
        }
    }
    ci.ci_inlinecrypt=false; ino.i_mode=2;
    assert(fscrypt_select_encryption_impl(&ci,false)==0 && !ci.ci_inlinecrypt);
    for(unsigned int count=1;count<=64;count++) {
        struct ufs_hba h={count};
        unsigned int expected=PROFILE ? (count<=2 ? 0 : (count<32?count:32)-2) : count;
        assert(ufshcd_crypto_qti_num_keyslots(&h)==expected);
        for(unsigned int slot=0;slot<expected;slot++) {
            unsigned int physical=ufshcd_crypto_qti_hw_keyslot(&h,slot);
            assert(physical==slot+(PROFILE?2:0) && physical<count);
            if(PROFILE) assert(physical>=2 && physical<=31);
        }
        assert(ufshcd_crypto_qti_hw_keyslot(&h,expected)==count);
        assert(ufshcd_crypto_qti_hw_keyslot(&h,UINT32_MAX)==count);
    }
    printf("PASS selection and keyslot boundaries, profile=%d\n",PROFILE);
}
'''

SCM_MOCK = r'''
#define BLK_CRYPTO_MAX_WRAPPED_KEY_SIZE 128
#define UFS_CE 10
#define SDCC_CE 20
#define ICE_CIPHER_MODE_XTS_256 3
#define TZ_ES_CONFIG_SET_ICE_KEY_CE_TYPE_ID 0x02000a05
#define TZ_ES_INVALIDATE_ICE_KEY_CE_TYPE_ID 0x02000a06
#define TZ_ES_CONFIG_SET_ICE_KEY_ID 0x02000a04
#define TZ_ES_INVALIDATE_ICE_KEY_ID 0x02000a03
#define TZ_ES_CONFIG_SET_ICE_KEY_CE_TYPE_PARAM_ID 6
#define TZ_ES_INVALIDATE_ICE_KEY_CE_TYPE_PARAM_ID 2
#define TZ_ES_CONFIG_SET_ICE_KEY_PARAM_ID 5
#define TZ_ES_INVALIDATE_ICE_KEY_PARAM_ID 1
struct crypto_vops_qti_entry { int unused; };
struct blk_crypto_key { unsigned int size; bool is_hw_wrapped; int crypto_mode; u8 raw[128]; };
struct qtee_shm { void *vaddr; uintptr_t paddr; };
struct scm_desc { unsigned int arginfo; uint64_t args[6]; };
static unsigned int storage_type=UFS_CE;
static unsigned int last_smc, calls; static struct scm_desc last_desc; static u8 firmware_key[128];
static int injected_error;
static int qtee_shmbridge_allocate_shm(unsigned int s, struct qtee_shm *m) {
    m->vaddr=calloc(1,s); m->paddr=(uintptr_t)m->vaddr; return m->vaddr?0:-ENOMEM;
}
static void qtee_shmbridge_free_shm(struct qtee_shm *m) { free(m->vaddr); }
#define dmac_flush_range(a,b) ((void)0)
static void memzero_explicit(void *p, size_t n) { volatile u8 *q=p; while(n--) *q++=0; }
static void __cpu_to_be32s(u32 *v) { *v=__builtin_bswap32(*v); }
static int scm_call2_noretry(unsigned int id, struct scm_desc *d) {
    calls++; last_smc=id; last_desc=*d;
    if(d->arginfo>=5) memcpy(firmware_key,(void *)(uintptr_t)d->args[1],d->args[2]);
    return injected_error;
}
'''

SCM_TEST = r'''
int main(void) {
    struct blk_crypto_key k={64,false,BLK_ENCRYPTION_MODE_AES_256_XTS,{0}};
    /* fscrypt supplies words already swapped; TEE must receive the original KDF output. */
    for(unsigned int i=0;i<64;i++) k.raw[i]=(u8)(i^3);
    assert(crypto_qti_program_key(NULL,&k,2,8,0)==0);
    assert(last_smc==(PROFILE?0x02000a04:0x02000a05));
    assert(last_desc.arginfo==(PROFILE?5:6));
    assert(last_desc.args[0]==2 && last_desc.args[2]==64 && last_desc.args[3]==3 && last_desc.args[4]==8);
    assert(last_desc.args[5]==(PROFILE?0:UFS_CE));
    for(unsigned int i=0;i<64;i++) assert(firmware_key[i]==i);
    assert(crypto_qti_invalidate_key(NULL,31)==0);
    assert(last_smc==(PROFILE?0x02000a03:0x02000a06));
    assert(last_desc.arginfo==(PROFILE?1:2));
    assert(last_desc.args[0]==31 && last_desc.args[1]==(PROFILE?0:UFS_CE));
    injected_error=-EIO; assert(crypto_qti_program_key(NULL,&k,2,8,0)==-EIO); injected_error=0;
    if(PROFILE) {
        unsigned int previous=calls;
        assert(crypto_qti_program_key(NULL,&k,0,8,0)==-EOPNOTSUPP);
        assert(crypto_qti_program_key(NULL,&k,1,8,0)==-EOPNOTSUPP);
        assert(crypto_qti_program_key(NULL,&k,32,8,0)==-EOPNOTSUPP);
        assert(crypto_qti_invalidate_key(NULL,0)==-EOPNOTSUPP);
        assert(crypto_qti_invalidate_key(NULL,32)==-EOPNOTSUPP);
        k.is_hw_wrapped=true; assert(crypto_qti_program_key(NULL,&k,2,8,0)==-EOPNOTSUPP);
        k.is_hw_wrapped=false; k.size=32; assert(crypto_qti_program_key(NULL,&k,2,8,0)==-EOPNOTSUPP);
        k.size=64; storage_type=SDCC_CE; assert(crypto_qti_program_key(NULL,&k,2,8,0)==-EOPNOTSUPP);
        assert(calls==previous);
    }
    printf("PASS mocked SCM arguments, endian and error propagation, profile=%d\n",PROFILE);
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel", type=Path, default=ROOT / "kernel-4.19")
    parser.add_argument("--cc", nargs="+", default=[str(ROOT / ".tools/python/ziglang/zig.exe"), "cc"])
    args = parser.parse_args()
    out = ROOT / "out/host-checks"
    out.mkdir(parents=True, exist_ok=True)
    paths = ["fs/crypto/inline_crypt.c", "drivers/scsi/ufs/ufshcd-crypto-qti.c", "drivers/soc/qcom/crypto-qti-tz.c"]
    src = [(args.kernel / p).read_text() for p in paths]
    selection = COMMON + function(src[0], "fscrypt_select_encryption_impl")
    selection += function(src[1], "ufshcd_crypto_qti_num_keyslots")
    selection += function(src[1], "ufshcd_crypto_qti_hw_keyslot") + SELECTION_TEST
    scm = COMMON + SCM_MOCK + function(src[2], "crypto_qti_program_key")
    scm += function(src[2], "crypto_qti_invalidate_key") + SCM_TEST
    results = []
    for name, content in [("selection", selection), ("scm", scm)]:
        file = out / (name + ".c")
        file.write_text(content, newline="\n")
        for profile in [0, 1]:
            exe = out / (name + str(profile) + (".exe" if sys.platform == "win32" else ""))
            cmd = args.cc + ["-std=gnu11", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-Wno-unused-parameter", "-Wno-sign-compare", "-DPROFILE=" + str(profile), str(file), "-o", str(exe)]
            subprocess.run(cmd, check=True)
            result = subprocess.check_output([str(exe)], text=True).strip()
            print(result)
            results.append(result)
    record = {"scope": "Host-compiled extracted functions with mock kernel/TEE dependencies. Not a kernel build or device test.", "results": results,
              "source_sha256": {p: hashlib.sha256((args.kernel / p).read_bytes()).hexdigest() for p in paths}}
    (out / "results.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
