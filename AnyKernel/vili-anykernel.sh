#!/sbin/sh
# Isolate kernel compatibility to the kernel; recovery and vendor device trees stay as backed up.
properties() { '
kernel.string=vili current KernelSU-Next + SUSFS 2.3.0
do.devicecheck=1
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=0
device.name1=vili
supported.versions=16.0
'; }

# Follow the current slot and preserve verification flags; never switch slots or touch vendor_boot.
BLOCK=boot;
IS_SLOT_DEVICE=1;
RAMDISK_COMPRESSION=auto;
PATCH_VBMETA_FLAG=0;
. tools/ak3-core.sh;

# Skip ramdisk edits and generic partition flashing to isolate the new Image.
split_boot;
flash_boot;
