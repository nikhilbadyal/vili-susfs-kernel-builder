# vili boot baseline

The earlier artifact compiled successfully but rebooted after reaching Android's boot animation. The original boot and vendor_boot images were restored and verified against their backups; Android and KernelSU 33294 work again. No new manager or SUSFS helper was installed. Persistent logs only contained an earlier successful Titanic boot, and pstore was empty, so the precise failure is not established.

The failed artifact used `vili_ksu-302` (`d043cb6a`) and its modular QGKI configuration. The working TitanicExtended kernel uses built-in device drivers and additional filesystem, RCU and cgroup options. The published `lineage-24.0-20260929` source at `3679ab828bc4464e4e41152154ca0f5c6ed361e6` resolves the working configuration with substantially fewer differences. Its branch date matches the working kernel's build date, but this does not establish that it is the exact Titanic source revision.

`configs/vili-working.config` was extracted from the verified original boot image. The baseline seeds `olddefconfig` with that complete configuration. The verifier requires the original enabled and disabled options, including driver linkage, with these explicit exceptions:

- KernelSU and its hook option are absent to isolate ROM compatibility before adding root and SUSFS separately.
- Compiler probes are regenerated using LLVM 18; the local version is `-vili-baseline`.
- The published source lacks Titanic's BORE scheduler, SSG I/O scheduler, Oplus CPU-frequency bouncing and configurable default zram compression additions. Its zram implementation selects LZO support; LZ4 remains available for runtime selection.

The artifact contains only Image, the pinned AnyKernel tools/installer, and build metadata. Its script calls `split_boot` and `flash_boot` on the current boot slot. It does not call the generic flashing functions, package modules, modify the ramdisk contents, supply device trees, change slots or request vbmeta patching. Existing boot and vendor_boot backups remain the recovery path. This is a diagnostic package, not the finished current-KernelSU/SUSFS kernel.

Verification includes the resolved and embedded configurations, ARM64 Image magic, source pin, installer identity, and an allowlist excluding secondary partition payloads. Successful compilation still requires device boot verification. The baseline gate was also checked against the failed configuration and deliberate Wi-Fi linkage/cgroup regressions; all were rejected.

For a temporary boot test, `scripts/repack-vili-boot.py ORIGINAL_BOOT IMAGE OUTPUT` accepts only the observed v3/4096-byte boot layout. It preserves the original header fields and compressed ramdisk bytes, replaces the kernel, and omits partition padding/AVB footer for downloading to the already verified unlocked bootloader. It writes only a host file; `fastboot boot OUTPUT` is a separate operation. A normal reboot returns to the installed Titanic boot image. Original-kernel round-trip testing reproduced the entire original image payload byte for byte, and an unsupported header was rejected.
