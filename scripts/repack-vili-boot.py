#!/usr/bin/env python3
"""Prepare a temporary fastboot boot image while preserving the known-working v3 header and compressed ramdisk."""

from pathlib import Path
import struct
import sys


def repack(original, kernel):
    """Accept only vili's observed Android boot v3 layout; never guess another header format."""
    assert original[:8] == b'ANDROID!'
    assert struct.unpack_from('<I', original, 40)[0] == 3, 'Expected boot header v3'
    assert struct.unpack_from('<I', original, 20)[0] == 1580, 'Unexpected v3 header size'
    assert kernel[56:60] == b'ARMd', 'Expected an uncompressed ARM64 Image'
    old_kernel_size, ramdisk_size = struct.unpack_from('<II', original, 8)
    # Header v3 fixes the alignment at 4096; retain every header field except kernel size.
    page = 4096
    old_ramdisk_offset = page + ((old_kernel_size + page - 1) // page) * page
    ramdisk = original[old_ramdisk_offset:old_ramdisk_offset + ramdisk_size]
    assert len(ramdisk) == ramdisk_size and ramdisk[:2] == b'\x1f\x8b', 'Original gzip ramdisk is missing'
    header = bytearray(original[:page])
    struct.pack_into('<I', header, 8, len(kernel))
    # Temporary boot on the verified unlocked device omits the installed backup's partition padding/AVB footer.
    return bytes(header) + kernel + bytes(-len(kernel) % page) + ramdisk + bytes(-len(ramdisk) % page)


# This command writes only a host file; device boot/flash commands are deliberately separate.
if __name__ == '__main__':
    original_path, kernel_path, output_path = map(Path, sys.argv[1:])
    result = repack(original_path.read_bytes(), kernel_path.read_bytes())
    assert not output_path.exists(), 'Refusing to overwrite an existing boot image'
    output_path.write_bytes(result)
    print(f'Prepared {output_path}: {len(result)} bytes; original compressed ramdisk preserved')
