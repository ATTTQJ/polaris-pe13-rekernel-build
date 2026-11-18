"""Exercise extracted wire8 command filtering and monitored UID state."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from run_host_checks import function

ROOT=Path(__file__).resolve().parents[1]
MOCK=r'''
#undef NDEBUG
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#define CONFIG_PROC_FS 1
#define CONFIG_REKERNEL_NETWORK 1
#define CAP_NET_ADMIN 12
#define REKERNEL_NET_UID_MAX 32
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
typedef unsigned uid_t;
static uid_t rekernel_net_uids[32];
static bool rekernel_net_uids_full;
static int rekernel_net_uids_lock;
static bool admin=true;
static unsigned removed,locks;
static void *rekernel_dir=(void *)1;
struct nlmsghdr { unsigned len; int payload[2]; };
struct sk_buff { unsigned len; struct nlmsghdr head; };
static bool netlink_capable(struct sk_buff *s,int c) { (void)s;assert(c==12);return admin; }
static unsigned nlmsg_total_size(unsigned n) { return n+16; }
static struct nlmsghdr *nlmsg_hdr(struct sk_buff *s) { return &s->head; }
static bool nlmsg_ok(struct nlmsghdr *h,unsigned n) { return h->len>=16 && h->len<=n; }
static unsigned nlmsg_len(struct nlmsghdr *h) { return h->len-16; }
static void *nlmsg_data(struct nlmsghdr *h) { return h->payload; }
static void proc_remove(void *p) { assert(p);removed++; }
static void spin_lock_bh(int *p) { (void)p;assert(!locks);locks++; }
static void spin_unlock_bh(int *p) { (void)p;assert(locks==1);locks--; }
'''
TEST=r'''
int main(void) {
    struct sk_buff s={24,{24,{2,10001}}};
    admin=false;netlink_rcv_msg(&s);assert(!net_uid_monitored(10001));
    admin=true;s.len=8;netlink_rcv_msg(&s);assert(!net_uid_monitored(10001));
    s.len=24;s.head.len=32;netlink_rcv_msg(&s);assert(!net_uid_monitored(10001));
    s.head.len=20;netlink_rcv_msg(&s);assert(!net_uid_monitored(10001));
    s.head.len=24;netlink_rcv_msg(&s);assert(net_uid_monitored(10001));
    netlink_rcv_msg(&s);assert(rekernel_net_uids[1]==0 && locks==0);
    s.head.payload[1]=0;netlink_rcv_msg(&s);assert(rekernel_net_uids[1]==0);
    s.head.payload[0]=99;netlink_rcv_msg(&s);assert(rekernel_dir && !removed);
    for(unsigned i=1;i<33;i++) { s.head.payload[0]=2;s.head.payload[1]=10001+i;netlink_rcv_msg(&s); }
    assert(rekernel_net_uids_full && net_uid_monitored(19999) && !locks);
    s.head.payload[0]=1;s.head.len=20;netlink_rcv_msg(&s);
    assert(!rekernel_dir && removed==1);netlink_rcv_msg(&s);assert(removed==1);
    puts("PASS wire8 command capability/length checks, UID registration, deduplication and existing full-list fallback");
}
'''


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--kernel',type=Path,default=ROOT/'kernel-4.19')
    p.add_argument('--cc',nargs='+',default=[str(ROOT/'.tools/python/ziglang/zig.exe'),'cc'])
    args=p.parse_args()
    paths=['drivers/rekernel/rekernel.c','drivers/rekernel/rekernel.h','drivers/rekernel/Kconfig','drivers/rekernel/Makefile',
           'drivers/android/binder.c','kernel/signal.c','net/ipv4/tcp_ipv4.c','net/ipv6/tcp_ipv6.c','drivers/Kconfig','drivers/Makefile']
    text=(args.kernel/paths[0]).read_text()
    helpers=function(text,'net_uid_monitored')+function(text,'netlink_rcv_msg')
    assert 'late_initcall(start_rekernel)' in text and 'smp_store_release(&rekernel_ready, true)' in text
    assert 'smp_load_acquire(&rekernel_ready)' in function(text,'rekernel_tcp_notify')
    for version,path in [(4,'net/ipv4/tcp_ipv4.c'),(6,'net/ipv6/tcp_ipv6.c')]:
        assert f'rekernel_tcp_notify(sk, skb, {version});' in (args.kernel/path).read_text()
    binder=(args.kernel/'drivers/android/binder.c').read_text()
    assert binder.index('binder_trans_handler(proc->pid') < binder.index('trace_binder_transaction(reply, t, target_node)')
    out=ROOT/'out/host-checks';out.mkdir(exist_ok=True)
    source=out/'rekernel_compat.c';source.write_text(MOCK+helpers+TEST,newline='\n')
    exe=out/('rekernel_compat'+('.exe' if sys.platform=='win32' else ''))
    subprocess.run(args.cc+['-std=gnu11','-O1','-Wall','-Wextra','-Werror',str(source),'-o',str(exe)],check=True)
    result=subprocess.check_output([str(exe)],text=True).strip();print(result)
    (out/'rekernel-compat-results.json').write_text(json.dumps({'scope':'Extracted command parser/UID tracking and source hook checks; not a kernel, network or app interop test','result':result,
        'source_sha256':{name:hashlib.sha256((args.kernel/name).read_bytes()).hexdigest() for name in paths}},indent=2)+'\n')


if __name__=='__main__':
    main()
