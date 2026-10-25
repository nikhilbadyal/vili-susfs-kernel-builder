# vili boot baseline

The earlier artifact compiled successfully but rebooted after reaching Android's boot animation. The original boot and vendor_boot images were restored and verified against their backups; Android and KernelSU 33294 work again. No new manager or SUSFS helper was installed. Persistent logs only contained an earlier successful Titanic boot, and pstore was empty, so the precise failure is not established.

The failed artifact used `vili_ksu-302` (`d043cb6a`) and its modular QGKI configuration. The working TitanicExtended kernel uses built-in device drivers and additional filesystem, RCU and cgroup options. The published `lineage-24.0-20260929` source at `3679ab828bc4464e4e41152154ca0f5c6ed361e6` resolves the working configuration with substantially fewer differences. Its branch date matches the working kernel's build date, but this does not establish that it is the exact Titanic source revision.

`configs/vili-working.config` was extracted from the verified original boot image. The baseline seeds `olddefconfig` with that complete configuration. The verifier requires the original enabled and disabled options, including driver linkage, with these explicit exceptions:

- KernelSU and its hook option are absent to isolate ROM compatibility before adding root and SUSFS separately.
- Compiler probes are regenerated using LLVM 18; the local version is `-vili-baseline`.
- The published source lacks Titanic's BORE scheduler, SSG I/O scheduler, Oplus CPU-frequency bouncing and configurable default zram compression additions. Its zram implementation selects LZO support; LZ4 remains available for runtime selection.

Qualcomm's selected Lahaina techpack `.conf` files separately force display, camera and audio into modules; these settings are absent from `.config`. The working phone's display module exposes built-in parameters without a loadable module's initstate/refcount files, and `/proc/modules` is empty. `patches/vili-builtin-techpacks.patch` makes those selected techpacks built-in. The build requires display, camera and audio definitions in the linked `vmlinux`; a matching `.config` alone is insufficient. No separate vendor module package is installed during this diagnostic test.

Built-in WLAN exposes two private helper names that collide with platform IPA and core nl80211 definitions at the vmlinux link step. `patches/vili-builtin-wlan.patch` namespaces WLAN's readiness helper and CLD80211 header helper, including their declarations and callers. The platform/core APIs and helper behavior are unchanged; there are no alias symbols or linker overrides.

The artifact contains only Image, the pinned AnyKernel tools/installer, and build metadata. Its script calls `split_boot` and `flash_boot` on the current boot slot. It does not call the generic flashing functions, package modules, modify the ramdisk contents, supply device trees, change slots or request vbmeta patching. Existing boot and vendor_boot backups remain the recovery path. This is a diagnostic package, not the finished current-KernelSU/SUSFS kernel.

Verification includes the resolved and embedded configurations, ARM64 Image magic, source pin, installer identity, and an allowlist excluding secondary partition payloads. Successful compilation still requires device boot verification. The baseline gate was also checked against the failed configuration and deliberate Wi-Fi linkage/cgroup regressions; all were rejected.

For a temporary boot test, `scripts/repack-vili-boot.py ORIGINAL_BOOT IMAGE OUTPUT` accepts only the observed v3/4096-byte boot layout. It preserves the original header fields and compressed ramdisk bytes, replaces the kernel, and omits partition padding/AVB footer for downloading to the already verified unlocked bootloader. It writes only a host file; `fastboot boot OUTPUT` is a separate operation. A normal reboot returns to the installed Titanic boot image. Original-kernel round-trip testing reproduced the entire original image payload byte for byte, and an unsupported header was rejected.


## Runtime result and return to the combined goal

Run 40185942686 produced a baseline that booted temporarily with `fastboot boot`. Android reported `sys.boot_completed=1`, the display/zygote/audio/camera services ran, and the camera service enumerated eight devices. Wi-Fi failed: the HAL could not access its driver control node. The candidate lacked `/dev/wlan`; the installed Titanic kernel exposes `/dev/wlan`, and its Wi-Fi works. A normal reboot returned to Titanic, and both original boot-partition hashes were reverified unchanged.

The companion device tree's `BoardConfigCommon.mk` explicitly configures `WIFI_DRIVER_STATE_CTRL_PARAM := "/dev/wlan"` with ON/OFF commands. The vendor WLAN source instead selected a deferred sysfs loader in built-in mode. The combined candidate removes that obsolete loader and initializes the existing character-device control path for built-in operation as well. The host test reproduces the original missing-node path and verifies the corrected path.

The workflow has now returned to the requested combined current KernelSU-Next/API 5 + SUSFS 2.3.0 artifact. `verify-vili-profile.py` checks the original hardware policy, linked drivers and boot-only package; `verify-vili.py` checks the released manager contract and linked root/SUSFS control. Neither the combined candidate's boot nor its Wi-Fi/SUSFS runtime is claimed until device verification succeeds.
