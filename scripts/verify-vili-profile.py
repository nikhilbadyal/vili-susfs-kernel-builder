#!/usr/bin/env python3
"""Gate the combined kernel against the working device configuration and kernel-only installation contract."""

import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile


def options(content):
    """Include explicit disabled settings to detect changed defaults as well as lost options."""
    values = dict(re.findall(r'^(CONFIG_\w+)=(.*)$', content, re.M))
    values.update({key: 'n' for key in re.findall(r'^# (CONFIG_\w+) is not set$', content, re.M)})
    return values


def verify_config(content):
    """Permit documented source/toolchain differences while retaining original driver linkage."""
    original = options(Path('configs/vili-working.config').read_text())
    resolved = options(content)
    # These Titanic performance additions are absent from the published Lineage source.
    absent = {'CONFIG_MQ_IOSCHED_SSG', 'CONFIG_MQ_IOSCHED_SSG_CGROUP',
              'CONFIG_OPLUS_FEATURE_CPUFREQ_BOUNCING', 'CONFIG_SCHED_BORE',
              'CONFIG_ZRAM_DEF_COMP', 'CONFIG_ZRAM_DEF_COMP_LZ4'}
    # Compiler probes are regenerated; the combined kernel has a distinct version suffix.
    metadata = {'CONFIG_AS_VERSION', 'CONFIG_CC_VERSION_TEXT', 'CONFIG_CLANG_VERSION', 'CONFIG_LOCALVERSION'}
    # This source selects LZO for zram unconditionally; LZ4 remains available for the ROM's runtime selection.
    selected = {'CONFIG_CRYPTO_LZO', 'CONFIG_LZO_COMPRESS', 'CONFIG_LZO_DECOMPRESS'}
    for key, value in original.items():
        if key in metadata:
            continue
        expected = 'n' if key in absent else value
        if key in selected:
            expected = 'y'
        assert resolved.get(key, 'n') == expected, f'{key}: expected {expected}, resolved {resolved.get(key, "n")}'
    assert resolved['CONFIG_LOCALVERSION'] == '"-vili-ksun-susfs"'
    assert resolved.get('CONFIG_LOCALVERSION_AUTO', 'n') == 'n'
    assert resolved.get('CONFIG_KSU_SUSFS', 'n') == 'y'
    print('Working device configuration preserved with KernelSU and SUSFS enabled')


def configured():
    """Record the fetched source and resolved config before compilation."""
    config = Path('kernel/out/.config').read_text()
    verify_config(config)
    revision = subprocess.check_output(['git', '-C', 'kernel', 'rev-parse', 'HEAD'], text=True).strip()
    # Do not let a moving upstream branch silently replace the reviewed baseline.
    assert revision == '3679ab828bc4464e4e41152154ca0f5c6ed361e6'
    info = {'kernel_ref': revision, 'purpose': 'current KernelSU-Next API 5 and SUSFS 2.3.0',
            'techpack_patch_sha256': hashlib.sha256(Path('patches/vili-builtin-techpacks.patch').read_bytes()).hexdigest(),
            'wlan_control_patch_sha256': hashlib.sha256(Path('patches/vili-wlan-control.patch').read_bytes()).hexdigest(),
            'wlan_patch_sha256': hashlib.sha256(Path('patches/vili-builtin-wlan.patch').read_bytes()).hexdigest(),
            'config_sha256': hashlib.sha256(config.encode()).hexdigest()}
    Path('profile-info.json').write_text(json.dumps(info, indent=2) + '\n')


def compiled():
    """Require real definitions from all three techpacks in vmlinux, rather than separate modules."""
    symbols = {line.split()[-1].split('.')[0] for line in
               Path('kernel/out/defined-symbols.txt').read_text().splitlines() if line.split()}
    for symbol in ['msm_drm_bind', 'camera_init', 'msm_asoc_machine_probe']:
        assert symbol in symbols, f'Techpack is missing from vmlinux: {symbol}'
    # The built-in entrypoint must expose the HAL character device, not retain the removed deferred loader.
    assert 'hdd_module_init' in symbols and 'wlan_init_sysfs' not in symbols
    print('Display, camera, audio and WLAN initialization are linked into vmlinux')


def package():
    """Inspect the shipped config and exclude secondary partition payloads."""
    with zipfile.ZipFile('vili-current-api-susfs.zip') as archive:
        assert archive.testzip() is None
        assert all(name in {'Image', 'anykernel.sh', 'profile-info.json', 'build-info.json'} or
                   name.startswith(('tools/', 'META-INF/')) for name in archive.namelist())
        image = archive.read('Image')
        assert image[56:60] == b'ARMd'
        start = image.index(b'IKCFG_ST') + 8
        end = image.index(b'IKCFG_ED', start)
        config = gzip.decompress(image[start:end]).decode()
        verify_config(config)
        assert config == Path('kernel/out/.config').read_text()
        assert archive.read('anykernel.sh') == Path('AnyKernel/vili-anykernel.sh').read_bytes()
        assert json.loads(archive.read('profile-info.json')) == json.loads(Path('profile-info.json').read_text())
        print('Verified embedded config and boot-only combined kernel installer')


# Keep config and package stages explicit so one cannot stand in for the other.
if __name__ == '__main__':
    {'configured': configured, 'compiled': compiled, 'package': package}[sys.argv[1]]()
