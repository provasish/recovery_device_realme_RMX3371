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
