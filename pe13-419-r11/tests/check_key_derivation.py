"""Exercise real key-setup dispatch with a synthetic AES-ECB known-answer stub.

The AES provider is mocked; this checks the selected path and endian conversion,
not the kernel crypto API implementation or any device secret.
"""
import json
from pathlib import Path
import subprocess
from run_host_checks import function

ROOT = Path(__file__).resolve().parents[1]

MOCK = r'''
#undef NDEBUG
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;
typedef struct { u64 a,b; } siphash_key_t;
#define FSCRYPT_MAX_HW_WRAPPED_KEY_SIZE 128
#define FSCRYPT_MODE_PRIVATE 127
#define FSCRYPT_POLICY_FLAG_IV_INO_LBLK_32 16
#define SHA256_DIGEST_SIZE 32
#define GFP_NOFS 0
#define CONFIG_ENABLE_LEGACY_PFK PROFILE
#define IS_ENABLED(x) (x)
struct policy { int mode; struct { unsigned int flags; } v1; };
struct inode { u64 i_ino; };
struct mode { unsigned int keysize; };
struct fscrypt_info { struct policy ci_policy; struct inode *ci_inode; struct mode *ci_mode; u8 ci_nonce[16]; u32 ci_hashed_ino; bool_dummy_not_used; };
'''.replace(' bool_dummy_not_used;', '') + r'''
static int inline_enabled=1, derive_calls, direct_calls, software_calls, injected_error;
static u8 captured[64];
static const u8 expected[64] = {
0x0a,0x94,0x0b,0xb5,0x41,0x6e,0xf0,0x45,0xf1,0xc3,0x94,0x58,0xc6,0x53,0xea,0x5a,
0x07,0xfe,0xef,0x74,0xe1,0xd5,0x03,0x6e,0x90,0x0e,0xee,0x11,0x8e,0x94,0x92,0x93,
0x5b,0xe8,0x7e,0x2e,0x5b,0x44,0x7c,0x94,0x4b,0x21,0xc9,0xaf,0x77,0x56,0xc0,0xd8,
0x03,0xf2,0xc3,0xbd,0xca,0x82,0x6b,0xf0,0x82,0xd7,0xcf,0xb0,0x35,0xcd,0xb8,0xc1};
static int fscrypt_policy_contents_mode(const struct policy *p) { return p->mode; }
static int fscrypt_using_inline_encryption(struct fscrypt_info *c) { (void)c; return inline_enabled; }
static int fscrypt_do_sha256(const u8 *p,int n,u8 *o) { (void)p;(void)n;(void)o; abort(); }
static u64 siphash_1u64(u64 n, const siphash_key_t *k) { (void)n;(void)k; abort(); }
static void *kmalloc(unsigned int n,int f) { (void)f; return malloc(n); }
#define kzfree free
static void memzero_explicit(void *p,size_t n) { volatile u8 *q=p;while(n--)*q++=0; }
static void __cpu_to_be32s(u32 *v) { *v=__builtin_bswap32(*v); }
static int derive_key_aes(const u8 *master,const u8 *nonce,u8 *derived,unsigned int n) {
    derive_calls++; assert(n==64);
    for(unsigned int i=0;i<n;i++) assert(master[i]==i);
    for(unsigned int i=0;i<16;i++) assert(nonce[i]==i);
    if(injected_error) return injected_error;
    memcpy(derived,expected,n);return 0;
}
static int setup_v1_file_key_direct(struct fscrypt_info *c,const u8 *key) {
    (void)c;direct_calls++;memcpy(captured,key,64);return 0;
}
static int fscrypt_set_per_file_enc_key(struct fscrypt_info *c,const u8 *key) {
    (void)c;software_calls++;memcpy(captured,key,64);return 0;
}
'''

TEST = r'''
int main(void) {
    struct inode inode={42};struct mode mode={64};
    struct fscrypt_info ci={{127,{0}},&inode,&mode,{0},0};u8 master[64];
    for(unsigned int i=0;i<64;i++)master[i]=(u8)i;
    for(unsigned int i=0;i<16;i++)ci.ci_nonce[i]=(u8)i;
    assert(setup_v1_file_key_derived(&ci,master)==0);
    assert(derive_calls==PROFILE && direct_calls==1 && software_calls==0);
    for(unsigned int i=0;i<64;i++)assert(captured[i]==(PROFILE?expected[i^3]:(i^3)));
    ci.ci_policy.mode=1;derive_calls=0;direct_calls=0;software_calls=0;
    assert(setup_v1_file_key_derived(&ci,master)==0);
    assert(derive_calls==1 && software_calls==1 && direct_calls==0);
    assert(!memcmp(captured,expected,64));
    ci.ci_policy.mode=127;inline_enabled=0;derive_calls=0;software_calls=0;
    assert(setup_v1_file_key_derived(&ci,master)==0);
    assert(derive_calls==1 && software_calls==1);
    inline_enabled=1;injected_error=-EIO;direct_calls=0;
    if(PROFILE)assert(setup_v1_file_key_derived(&ci,master)==-EIO && direct_calls==0);
    printf("PASS real key-setup dispatch and endian conversion (AES mock), profile=%d\n",PROFILE);
}
'''


def main():
    source = (ROOT / 'kernel-4.19/fs/crypto/keysetup_v1.c').read_text()
    out = ROOT / 'out/host-checks'
    out.mkdir(parents=True, exist_ok=True)
    file = out / 'keysetup.c'
    file.write_text(MOCK + function(source, 'setup_v1_file_key_derived') + TEST, newline='\n')
    results = []
    for profile in [0, 1]:
        exe = out / ('keysetup' + str(profile) + '.exe')
        subprocess.run([str(ROOT / '.tools/python/ziglang/zig.exe'), 'cc', '-std=gnu11', '-O1', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare', '-DPROFILE=' + str(profile), str(file), '-o', str(exe)], check=True)
        result = subprocess.check_output([str(exe)], text=True).strip()
        print(result)
        results.append(result)
    (out / 'keysetup-results.json').write_text(json.dumps({'scope': 'Real key-setup function, mocked AES provider with synthetic expected vector. Not a device decryption test.', 'results': results}, indent=2) + '\n')


if __name__ == '__main__':
    main()
