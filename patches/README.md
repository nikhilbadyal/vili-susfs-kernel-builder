# vili current-API SUSFS integration

The build targets Xiaomi 11T Pro (`vili`), Linux 5.4.302, the released KernelSU-Next v3.4.2 manager and its UAPI 5. Nothing in this build changes the reported ABI or inflates the kernel version to satisfy the manager.

## Pinned sources

- Kernel: `Spanish-or-Vanish/kernel_xiaomi_sm8350` at `d043cb6acb952f44241c9af113ebd4f8865dda73`.
- Driver: official `KernelSU-Next/KernelSU-Next` legacy commit `465490a26667ba4cf00b3be975a7e28e53978829` (2026-10-15). This includes the official v3.4.2 legacy backports in `e3292239`. Its closest tag is still `v3.4.0-legacy`; the real source-derived driver version is **33314**, UAPI **5**. The subsequent legacy commit introduces development UAPI 6, which does not match the released v3.4.2 manager.
- Manager contract: official v3.4.2 commit `4c706b5938665866ebe16944a481a7b91e3396af`, minimum driver version **33188**, UAPI **5**.
- VFS patch reference: `JackA1ltman/NonGKI_Kernel_Build_2nd` at `dcd789634247c77d8549a42aef232c680a905585`, `Patches/Patch/susfs_patch_to_5.4.patch` (SUSFS **v2.3.0**). The upstream SUSFS work is by simonpunk; retain the source license and attribution.
- SUSFS command/config reference: `pershoot/KernelSU-Next` `dev-susfs` at `d21e0a66c887ae4bc75b7c9f83e41761819ec09a`. Its development kernel implementation is not substituted for the maintained non-GKI driver.
- AnyKernel3: `loystonpais/AnyKernel3` at `a4ffe92b9b05b058960079e9b6b029f7dfe954f2`.

## End-state patches

`anykernel-ksunext.patch` detects the installed root daemon instead of a manager package directory that may be encrypted in recovery. It installs the helper as a directory module for current KernelSU-Next, removes obsolete ext4 module-image staging, and aborts if systemless storage or the root installation is unavailable. A systemless request must never fall through to direct vendor/system writes.

`vili-susfs-2.3.0.patch` replaces the existing v1.5.9 VFS implementation. It removes the old SUSFS import (`cd949e04`) and old manual root call sites (`30fdd274`), applies the supplied v2.3.0 filesystem changes, and resolves the two map-display hunks around the kernel's existing vili presentation code. The port supplies the missing stat definitions and uses the upstream filename helpers in the SD-card monitor, matching vili's qstr-based fsnotify ABI. The init transition exception uses the current driver's `ksu` SELinux domain. Device drivers, DTB selection and the proven compiler recipe are preserved.

`ksu-legacy-susfs.patch` adds the VFS command dispatcher, SID cache and process-flag updates to the official legacy driver. It keeps that driver's maintained kprobe root hooks, permission checks, manager detection, module unmount mechanism and UAPI. Root-only SUSFS commands use its existing reboot control hook and defer execution to task work before userspace resumes, so sleeping handlers never run inside a kprobe callback. The VFS flags are refreshed as apps specialize, and SUSFS path-refresh work runs after the existing unmount handler. No old command aliases or deprecated operation emulation are provided.

The integration is custom and needs runtime testing. Compilation proves neither successful boot nor effective hiding in an app. The previously installed SUSFS 1.x module is not validated for SUSFS 2.3.0; choose a matching 2.3.0 userspace companion before enabling automatic boot scripts.

## Verification and execution

Dispatch `Build vili KSU-Next SUSFS` on the feature branch. The workflow strictly applies both patches, checks resolved configuration and the actual released manager contract, then builds and checks defined symbols, compiler-recorded version, the image's embedded configuration, device-tree formats, module ELF headers and AnyKernel device targeting. The artifact includes `build-info.json` and `SHA256SUMS`.

For a prepared source tree, `python3 scripts/test-susfs-control.py kernel/KernelSU-Next/kernel/feature/susfs_control.c kernel/include/linux/susfs_def.h` checks deferred execution and failure cleanup with host stubs. CI compilation checks the actual kernel headers and ABI; this host test does not replace runtime testing.

The source tree already contains two vendor touchscreen `.rej` files unrelated to this integration. The verification checks for newly created untracked rejects rather than deleting those vendor files.

AnyKernel writes boot-related partitions, including vendor_boot. Keep the existing verified backups of boot_a, dtbo_a and vendor_boot_a before deciding to flash. This builder does not flash or reboot a device.
