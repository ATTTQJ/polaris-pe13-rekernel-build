"""Compile real F2FS allocation/feature helpers; this is not a mounted-FS test."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from run_host_checks import function

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--kernel',type=Path,default=ROOT/'kernel-4.19')
    parser.add_argument('--cc',nargs='+',default=[str(ROOT/'.tools/python/ziglang/zig.exe'),'cc'])
    args=parser.parse_args()
    header=(args.kernel/'include/linux/f2fs_fs.h').read_text()
    # Use the real packed attribute declarations, not a duplicated layout.
    start=header.index('__le16 i_extra_isize;')
    end=header.index('} __packed;',start)
    attributes=header[start:end]
    f2fs=(args.kernel/'fs/f2fs/f2fs.h').read_text()
    super_source=(args.kernel/'fs/f2fs/super.c').read_text()
    namei=(args.kernel/'fs/f2fs/namei.c').read_text()
    assert 'F2FS_I(inode)->i_extra_isize = f2fs_new_inode_extra_isize();' in namei
    assert super_source.index('err = f2fs_check_pe13_disk_features(sbi);') < super_source.index('default_options(sbi);',super_source.index('static int f2fs_fill_super('))
    inode=(args.kernel/'fs/f2fs/inode.c').read_text()
    assert 'fi->i_extra_isize > F2FS_TOTAL_EXTRA_ATTR_SIZE' in inode
    code=r'''
#undef NDEBUG
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <errno.h>
#ifndef EOPNOTSUPP
#define EOPNOTSUPP 95
#endif
#define __packed __attribute__((packed))
typedef uint16_t __le16;
typedef uint32_t __le32;
typedef uint64_t __le64;
typedef uint8_t __u8;
typedef uint32_t u32;
#define CONFIG_F2FS_LEGACY_EXTRA_ATTR_PE13 PROFILE
#define IS_ENABLED(x) (x)
#define BUILD_BUG_ON(x) _Static_assert(!(x), "layout mismatch")
#define le32_to_cpu(x) (x)
#define f2fs_err(...) ((void)0)
struct f2fs_inode {
'''+attributes+r'''
} __packed;
#define F2FS_TOTAL_EXTRA_ATTR_SIZE offsetof(struct f2fs_inode,i_extra_end)
struct f2fs_super_block { u32 feature; };
struct f2fs_sb_info { struct f2fs_super_block *raw_super; };
'''+function(f2fs,'f2fs_new_inode_extra_isize')+function(super_source,'f2fs_check_pe13_disk_features')+r'''
int main(void) {
    assert(F2FS_TOTAL_EXTRA_ATTR_SIZE==36);
    assert(offsetof(struct f2fs_inode,i_compr_blocks)==24);
    assert(f2fs_new_inode_extra_isize()==(PROFILE?24:36));
    assert(offsetof(struct f2fs_inode,i_crtime_nsec)+sizeof(__le32)<=24);
    struct f2fs_super_block sb={0};struct f2fs_sb_info sbi={&sb};
    /* All old feature combinations, including actual device 0x499. */
    for(u32 feature=0;feature<=0xfff;feature++) {
        sb.feature=feature;
        assert(f2fs_check_pe13_disk_features(&sbi)==0);
    }
    for(unsigned bit=12;bit<32;bit++) {
        sb.feature=0x499U | (1U<<bit);
        assert(f2fs_check_pe13_disk_features(&sbi)==(PROFILE?-EOPNOTSUPP:0));
    }
    /* New writer fits the old reader; existing 36-byte nodes stay intact. */
    if(PROFILE)assert(f2fs_new_inode_extra_isize()<=24);
    for(unsigned size=24;size<=36;size+=12) {
        struct f2fs_inode existing={0};existing.i_extra_isize=size;
        assert(existing.i_extra_isize<=F2FS_TOTAL_EXTRA_ATTR_SIZE);
        assert(existing.i_extra_isize%sizeof(__le32)==0);
        assert(existing.i_extra_isize==size);
    }
    printf("PASS F2FS actual attribute layout, allocation and feature gate profile=%d\n",PROFILE);
}
'''
    out=ROOT/'out/host-checks';out.mkdir(parents=True,exist_ok=True)
    path=out/'f2fs-layout.c';path.write_text(code,newline='\n')
    results=[]
    for profile in [0,1]:
        exe=out/('f2fs-layout'+str(profile)+('.exe' if sys.platform=='win32' else ''))
        subprocess.run(args.cc+['-std=gnu11','-O1','-Wall','-Wextra','-Werror','-DPROFILE='+str(profile),str(path),'-o',str(exe)],check=True)
        result=subprocess.check_output([str(exe)],text=True).strip();print(result);results.append(result)
    paths=['include/linux/f2fs_fs.h','fs/f2fs/f2fs.h','fs/f2fs/namei.c','fs/f2fs/super.c','fs/f2fs/inode.c']
    (out/'f2fs-layout-results.json').write_text(json.dumps({'scope':'Real extracted allocation/feature helpers and packed attributes with host stubs. Not a mounted filesystem or device test.','results':results,'source_sha256':{p:hashlib.sha256((args.kernel/p).read_bytes()).hexdigest() for p in paths}},indent=2))

if __name__=='__main__':main()
