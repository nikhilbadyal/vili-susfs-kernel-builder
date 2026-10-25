# Exercise the actual control implementation with host stubs to verify deferral and failure cleanup.
from pathlib import Path
import re
import subprocess
import tempfile
import sys
source = Path(sys.argv[1]).read_text()
source = re.sub(r'^#include.*\n', '', source, flags=re.M)
definitions = Path(sys.argv[2]).read_text()
commands = '\n'.join(re.findall(r'^#define CMD_SUSFS_\w+ 0x[0-9a-f]+.*$', definitions, re.M))
# The stubs fail if a sleeping handler executes while the simulated probe is active.
preamble = r'''
#include <assert.h>
#include <errno.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#define __user
#define noinline __attribute__((noinline))
#define GFP_ATOMIC 1
#define TWA_RESUME 1
#define KERNEL_SU_CONTEXT "u:r:ksu:s0"
#define current NULL
#define container_of(pointer, type, field) ((type *)((char *)(pointer) - offsetof(type, field)))
typedef unsigned int u32;
struct callback_head { void (*func)(struct callback_head *); };
static struct callback_head *pending;
static int in_probe, queue_error, allocation_error, freed;
static void *kzalloc(size_t size, int flags) {
    /* Allocation from the probe must never request a sleeping allocator. */
    assert(in_probe && flags == GFP_ATOMIC);
    return allocation_error ? NULL : calloc(1, size);
}
static void kfree(void *pointer) { freed++; free(pointer); }
static int task_work_add(void *task, struct callback_head *work, int mode) {
    /* The command must complete on return to userspace in its original task. */
    (void)task; assert(mode == TWA_RESUME);
    if (queue_error) return queue_error;
    pending = work; return 0;
}
static void security_secctx_to_secid(const char *context, size_t length, u32 *sid) {
    (void)context; (void)length; *sid = 7;
}
static u32 current_sid(void) { return 7; }
'''
# Handler mappings are taken from the actual source, keeping this test focused on execution context.
handlers = sorted(set(re.findall(r'^        (susfs_\w+)\(arg\);', source, re.M)))
for handler in handlers:
    body = 'assert(!in_probe);'
    if handler == 'susfs_show_version':
        body += ' *(int *)*arg = 230;'
    else:
        body += ' (void)arg;'
    preamble += f'\nstatic void {handler}(void **arg) {{ {body} }}\n'
main = r'''
int main(void) {
    int reply = 0;
    /* A successful request must leave user data untouched until task work executes. */
    in_probe = 1;
    assert(ksu_susfs_schedule(CMD_SUSFS_SHOW_VERSION, &reply) == 0);
    assert(reply == 0 && pending && freed == 0);
    in_probe = 0;
    pending->func(pending); pending = NULL;
    assert(reply == 230 && freed == 1);
    /* A rejected queue must release its allocation and never call a handler. */
    in_probe = 1; queue_error = -ESRCH;
    assert(ksu_susfs_schedule(CMD_SUSFS_SHOW_VERSION, &reply) == -ESRCH);
    assert(!pending && freed == 2 && reply == 230);
    /* Allocation failure must not leave a queued callback or free an invalid pointer. */
    queue_error = 0; allocation_error = 1;
    assert(ksu_susfs_schedule(CMD_SUSFS_SHOW_VERSION, &reply) == -ENOMEM);
    assert(!pending && freed == 2);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    # Build a host executable; this validates control flow, while CI validates the real kernel headers and ABI.
    path = Path(directory)
    (path / 'control.c').write_text(preamble + commands + '\n' + source + main)
    subprocess.run(['clang', '-std=gnu11', str(path / 'control.c'), '-o', str(path / 'control')], check=True)
    subprocess.run([str(path / 'control')], check=True)
print('PASS: deferred execution, atomic allocation, queue rejection cleanup and allocation failure')
