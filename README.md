## Device specifications

| Device                  | Realme GT Neo 3T (5G)                                        |
| ----------------------- | :---------------------------------------------------------- |
| SoC                     | Qualcomm SM8250-AC Snapdragon 870 5G (7 nm)                 |
| CPU                     | Octa-core (1x3.2 GHz Kryo 585 & 3x2.42 GHz Kryo 585 & 4x1.80 GHz Kryo 585)|
| GPU                     | Adreno 650                                                  |
| Shipped Android version | Android 12.0 with Realme UI 3.0                             |
| Memory                  | 6/8/12 GB RAM                                                 |
| Storage                 | (128/256) / 256 GB                                          |
| Battery                 | Non-removable Li-Po 5000 mAh                                |
| Display                 | 1080 x 2400 pixels, 20:9 ratio, 6.62 inches AMOLED (~398 ppi density) |


## Device picture
![Realme GT Neo 3T](https://fdn2.gsmarena.com/vv/pics/realme/neo-3t-1.jpg "Realme GT Neo 3T")

## What works

- FBE + metadata decryption (stock realme UI and AOSP ROMs, with or without a PIN)
- Touch, vibration (aw8697), MTP, ADB, fastbootd, slot switching
- Installing stock realme UI and custom A/B ROM zips from storage or `adb sideload`
- **High-speed flash** (optional, see below)
- `lpdump`, `lptools` and `bootctl` for inspecting Super and slots

## Building

Use the TWRP `twrp-12.1` minimal manifest
(`https://github.com/minimal-manifest-twrp/platform_manifest_twrp_aosp`, branch `twrp-12.1`)
and this local manifest, e.g. `.repo/local_manifests/rmx3371.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <remote name="gh" fetch="https://github.com" />

  <project name="provasish/recovery_device_realme_RMX3371" path="device/realme/RMX3371" remote="gh" revision="3.7.0_12" />

  <!-- TWRP recovery source with high-speed flash -->
  <remove-project name="android_bootable_recovery" />
  <project name="provasish/android_bootable_recovery" path="bootable/recovery" remote="gh" revision="android-12.1" />
</manifest>
```

| Repository | Branch | Contents |
| ---------- | ------ | -------- |
| [provasish/recovery_device_realme_RMX3371](https://github.com/provasish/recovery_device_realme_RMX3371) | `3.7.0_12` | this device tree |
| [provasish/android_bootable_recovery](https://github.com/provasish/android_bootable_recovery) | `android-12.1` | TeamWin `android-12.1` plus high-speed flash and an honest slot-switch result |

The tree also builds against stock TeamWin `bootable/recovery` (drop the two
recovery lines); you just don't get high-speed flash, and otaripper goes unused.

`device/qcom/twrp-common`, `hardware/qcom/bootctrl` and `device/qcom/common` come
from the minimal manifest.

```bash
. build/envsetup.sh
lunch twrp_RMX3371-eng
mka recoveryimage
```

This also generates `out/target/product/RMX3371/twrp-installer-RMX3371.zip`
alongside `recovery.img`. The ZIP is rebuilt whenever the image or installer
sources change; `mka recoveryzip` is also available. Packaging requires host
`python3` and uses only its standard library. To package an existing image:

```bash
python3 device/realme/RMX3371/tools/build_recovery_installer.py \
  --image out/target/product/RMX3371/recovery.img \
  --output out/target/product/RMX3371/twrp-installer-RMX3371.zip
```

In an already working TWRP, use **Install** to flash the installer ZIP with
**High-speed flash off** (this is a recovery installer, not a payload ROM).
The ZIP is **unsigned**, so ZIP signature verification must be off; its embedded
SHA-256 detects damaged image contents but does not authenticate the publisher.
Keep a trusted copy of `recovery.img` on your PC for initial installation or
recovery through fastboot. This installer is intended for TWRP-compatible
recoveries, not stock recovery or Android's local-update screen.

The installer accepts the exact device aliases `RMX3371`, `RE54E4L1` and
`spartan`, checks the embedded image checksum, and validates **both** dedicated
128 MiB recovery block devices before writing. It writes the slot opposite
`ro.boot.slot_suffix` first, syncs, and checks the SHA-256 of the written image
bytes before proceeding to the booted slot. It never switches slots, repacks
boot, modifies vbmeta, or formats userdata. Installing both slots replaces any
other recovery previously installed on either slot. If a write or read-back
check fails, stop and reflash a known-good recovery through fastboot before
rebooting; the operation cannot roll back a partially written partition.

Host fixtures (ordinary temporary files, never real block devices):

```bash
python3 device/realme/RMX3371/tools/test_recovery_installer.py
```

The fixtures cover ZIP reproducibility, image header/size validation, build-rule
dependencies, device/slot checks, both-partition preflight, write order, corrupt
image rejection, write errors, read-back errors, and TWRP UI pipes with high
descriptor numbers. The installer refuses to flash if its UI pipe is unavailable.
A full Android/Kati build
and real-device flashing still need validation. On the first device test,
confirm both recovery slots boot afterward and the bootloader active slot did
not change.

The phone has `recovery_a` and `recovery_b`; flash both:

```bash
fastboot flash recovery_a out/target/product/RMX3371/recovery.img
fastboot flash recovery_b out/target/product/RMX3371/recovery.img
```

## Flashing ROMs

- Tick **Automatically Reflash TWRP after flashing a ROM** (A/B ROM zips also
  replace `recovery` on the slot they write).
- Copy the zip to internal storage and use **Install**; it is about three times
  faster than `adb sideload` over this phone's USB 2.0 link.
- Moving between stock realme UI and a custom ROM needs **Format Data**.
- Super is about 10.5 GiB and stock needs about 7.75 GiB, so two ROMs never fit
  side by side: every install reuses the current slot's Super space, and the
  current slot won't boot until the install finishes.

## High-speed flash

An optional install path for A/B ROM zips: otaripper
(`recovery/root/system/bin/otaripper`) decodes the payload with all CPU cores and
writes it straight into the inactive slot, then switches slots. Stock
RMX3371_14.0.0.2100 installs in about 70 s instead of about 320 s.

| Option | Default | What it does |
| ------ | ------- | ------------ |
| High-speed flash | off | use it for this install |
| verify images after writing | on | re-read every image from storage and check its SHA-256 |
| allow overwriting the current slot | off | needed on this phone, see Super above |
| also flash firmware | off | write modem, xbl, tz, ... too (always verified) |

Full OTA zips only. If high-speed flash can't take a zip and nothing has been
written yet, the install continues the normal way. To rebuild otaripper from
source run `tools/build_otaripper.sh` on an x86_64 Linux host.

Tested on device (RMX3371): stock realme UI 14.0.0.2100 with and without
firmware (73 s, all 22 firmware images verified), and an AOSP ROM (52 s).

## Kernel patch: f2fs inode size

`prebuilt/Image` is the stock realme UI 14 kernel with one instruction changed
by `tools/patch_f2fs_extra_isize.py`. On /data (larger than 32 GiB) the stock
kernel gives new f2fs inodes a 48-byte extra attribute area, which AOSP kernels
reject with "Structure needs cleaning", so anything TWRP wrote was unreadable
on AOSP ROMs. The patched kernel creates 36-byte inodes like the AOSP kernels
do, and still reads the 48-byte ones stock realme UI creates. If you replace
the kernel, run the script on the new `Image`; it refuses to touch a kernel
it doesn't recognize.

## Experimental recovery improvements

With the matching recovery-source changes, Advanced -> Copy Log offers
**Include Device Diagnostics**. It creates a unique `twrp-diagnostics-*`
directory on the selected storage containing recovery/kernel/logcat logs,
Super metadata for both slots, read-only bootctl queries, mounts, block links,
selected properties, and any existing pstore/last_kmsg files. Optional commands
have a 15-second timeout; missing tools and nonzero exits are recorded in
`status.txt`. No partitions are mounted by the collector and nothing is uploaded.
Logs can still contain personal information; inspect them before sharing.
This preserves available crash logs, not logs already overwritten by recovery.
The bundle is given the storage folder's owner with owner/group-only access,
so Android (media_rw) can open and delete it on internal storage.

The stock-OTA reserve helper now waits for an ext4/f2fs read-write userdata
mount and, when encrypted, successful TWRP decryption. TWRP never sets
`ro.crypto.state=unencrypted`, so an unset value counts as unencrypted (e.g.
right after Format Data) unless `/data/unencrypted/key/version` exists. It
preserves existing images, refuses conflicting nodes/symlinks, and creates
aliases only alongside `misc` under `/dev/block/by-name`. It no longer adds
them explicitly under `/dev/block/bootdevice/by-name` or requires a
world-writable script. Failed writes are retried every 2 seconds and logged
once; it only stops when an unexpected file or link is in the way.

High-speed flashing now requires readable Android OTA text metadata declaring
`ota-type=AB` and a `pre-device` matching this board's
`TARGET_OTA_ASSERT_DEVICE` aliases. Missing, oversized, duplicate, or mismatched
device metadata stops this path before payload writes; it does not fall back
to the normal installer. This checks package compatibility, not authenticity;
the existing ZIP signature-verification setting remains separate.

Host checks:

```bash
python3 device/realme/RMX3371/tools/test_recovery_helpers.py
c++ -std=c++17 -Wall -Wextra -Werror \
  -I bootable/recovery/twrpinstall/include \
  bootable/recovery/tests/ota_device_check_test.cpp -o /tmp/ota-device-test
/tmp/ota-device-test
```

These changes need a full recovery build and device validation. In particular,
test stock/custom OTA installation, decryption with and without a PIN, Format
Data followed by another install, slot switching, and diagnostic export to
internal storage and USB OTG. Host fixtures do not exercise real mount races,
Android init, the boot HAL, or the actual recovery command versions.

---
## Copyright notice
 ```
  /*
  *  Copyright (C) 2020-2021 The OrangeFox Recovery Project
  *
  * This program is free software: you can redistribute it and/or modify
  * it under the terms of the GNU General Public License as published by
  * the Free Software Foundation, either version 3 of the License, or
  * (at your option) any later version.
  *
  * This program is distributed in the hope that it will be useful,
  * but WITHOUT ANY WARRANTY; without even the implied warranty of
  * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  * GNU General Public License for more details.
  *
  * You should have received a copy of the GNU General Public License
  * along with this program.  If not, see <http://www.gnu.org/licenses/>.
  *
  */
  ```
