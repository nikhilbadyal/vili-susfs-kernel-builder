#!/usr/bin/env python3
"""Fail the build when the source, compiled driver, or flashable package misses the promised contract."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

KERNEL = Path('kernel')
DRIVER = KERNEL / 'KernelSU-Next'
INFO = Path('build-info.json')
REQUIRED = [
    'KPROBES', 'KRETPROBES', 'KSU', 'KSU_KPROBES_HOOK', 'THREAD_INFO_IN_TASK', 'IKCONFIG',
    'KSU_SUSFS', 'KSU_SUSFS_SUS_PATH', 'KSU_SUSFS_SUS_MOUNT',
    'KSU_SUSFS_SUS_KSTAT', 'KSU_SUSFS_SPOOF_UNAME', 'KSU_SUSFS_ENABLE_LOG',
    'KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS', 'KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG',
    'KSU_SUSFS_OPEN_REDIRECT', 'KSU_SUSFS_SUS_MAP',
]


def require_config(config):
    """Check resolved options; writing a defconfig does not prove Kconfig accepted them."""
    lines = set(config.splitlines())
    for option in REQUIRED:
        assert f'CONFIG_{option}=y' in lines, f'Missing CONFIG_{option}=y'
    assert 'CONFIG_KSU_MANUAL_HOOK=y' not in lines, 'Unexpected second root hook mechanism'


def git(path, *args):
    """Read provenance from the actual source checkout used by this job."""
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


def verify_sources():
    """Match the real legacy version and UAPI to the released manager without version overrides."""
    require_config((KERNEL / 'out/.config').read_text())
    uapi = (DRIVER / 'uapi/supercall.h').read_text()
    version = int(re.search(r'#define KERNEL_SU_UAPI_VERSION (\d+)', uapi)[1])
    manager_api = int(re.search(r'KERNEL_SU_UAPI_VERSION = (\d+)', Path('manager-supercall.h').read_text())[1])
    minimum = int(re.search(r'MINIMAL_SUPPORTED_KERNEL = (\d+)', Path('manager-Natives.kt').read_text())[1])
    # This offset is the pinned official legacy Kbuild formula, not a manager-acceptance override.
    kbuild = (DRIVER / 'kernel/Kbuild').read_text()
    assert 'expr 30000 + $(KSU_GIT_VERSION) + 289' in kbuild
    driver_version = 30000 + int(git(DRIVER, 'rev-list', '--count', 'HEAD')) + 289
    assert version == manager_api == 5, (version, manager_api)
    assert driver_version >= minimum, (driver_version, minimum)
    assert git(KERNEL, 'rev-parse', 'HEAD') == os.environ['KERNEL_REF']
    assert git(DRIVER, 'rev-parse', 'HEAD') == os.environ['KSU_REF']
    assert '#define SUSFS_VERSION "v2.3.0"' in (KERNEL / 'include/linux/susfs.h').read_text()
    # stat.c consumes SUSFS flags and app classification directly; catch a dropped include before the full build.
    assert '#include <linux/susfs_def.h>' in (KERNEL / 'fs/stat.c').read_text()
    # Rejected patches and surviving old manual hooks must never reach a flashable artifact.
    assert not any(name.endswith('.rej') for name in git(KERNEL, 'ls-files', '--others', '--exclude-standard').splitlines()), 'New patch rejection files remain'
    assert 'ksu_handle_execveat(' not in (KERNEL / 'fs/exec.c').read_text()
    metadata = {
        'kernel_commit': os.environ['KERNEL_REF'],
        'ksu_commit': os.environ['KSU_REF'],
        'ksu_version': driver_version,
        'ksu_upstream_tag': git(DRIVER, 'describe', '--tags', '--abbrev=0'),
        'ksu_uapi': version,
        'manager_release': 'v3.4.2',
        'manager_commit': os.environ['MANAGER_REF'],
        'manager_minimum_kernel': minimum,
        'susfs_version': 'v2.3.0',
        'builder_commit': git(Path('.'), 'rev-parse', 'HEAD'),
        'patches': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in Path('patches').glob('*.patch')},
    }
    INFO.write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata, indent=2))


def verify_compiled():
    """Verify linked symbols and the version passed to the actual compiler."""
    symbols = {line.split()[-1].split('.')[0] for line in (KERNEL / 'out/defined-symbols.txt').read_text().splitlines() if line.split()}
    for symbol in ['ksu_susfs_control', 'susfs_add_sus_path', 'susfs_add_sus_map', 'ksu_handle_sys_reboot']:
        assert symbol in symbols, f'Missing linked symbol: {symbol}'
    commands = [path.read_text() for path in (KERNEL / 'out/drivers/kernelsu').rglob('.init.o.cmd')]
    expected = json.loads(INFO.read_text())['ksu_version']
    assert any(f'-DKSU_VERSION={expected}' in command for command in commands), 'Compiled KSU version differs from verified source'
    print(f'Linked SUSFS control plane and KernelSU {expected} verified')



# Source/API and linked-control checks are independent of the boot-only packaging gate.
if __name__ == '__main__':
    {'sources': verify_sources, 'compiled': verify_compiled}[sys.argv[1]]()
