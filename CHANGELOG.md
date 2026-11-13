# Changelog

TWRP for the realme GT Neo 3T (RMX3371).

## Unreleased
- Experimental: device-metadata checks for high-speed flashing (matching recovery source required)
- Experimental: optional device diagnostic export from Copy Log, including existing pstore logs
- Reserve helper waits for mounted/decrypted userdata, preserves existing images and conflicting nodes, and avoids adding bootdevice slot aliases
- No more gray band at the top: the UI uses the full screen and the CPU temperature moved clear of the punch-hole camera
- CPU temperature now reads the CPU sensor (cpuss-0) instead of aoss0
- VBMeta System and VBMeta Vendor can be flashed and backed up (Install → Image, Backup)
- Files and folders TWRP writes to internal storage (backups, adb push, MTP) are now readable on AOSP ROMs.
  Before, Android showed "Structure needs cleaning" for them, and a folder containing one listed as empty

## 3.7.1_12-provasish-20261109

Download: [twrp_RMX3371.img](https://github.com/provasish/recovery_device_realme_RMX3371/releases/download/3.7.1_12-provasish-20261109/twrp_RMX3371.img) ([release page](https://github.com/provasish/recovery_device_realme_RMX3371/releases/tag/3.7.1_12-provasish-20261109))

Based on TWRP 3.7.1 (android-12.1) with the stock realme UI 14.0.0.2100 kernel.

### Highlights
- **High-speed flash** (new, optional): installs A/B ROM zips using all CPU cores and writes
  straight to the inactive slot. Stock realme UI installs in ~70 s instead of ~320 s, an AOSP ROM in ~50 s.
  Every image is re-read from storage and SHA-256 checked before the slot is switched.
- **Stock realme UI OTAs now install** from storage or sideload (previously failed with Error 7 / Error 5).
- **Reads /data written by stock realme UI**: switched to the stock kernel, dtb and dtbo.

### Fixes
- Decryption: restored the missing /metadata entry (FBE + metadata encryption), with or without a PIN
- Slot switching now really reaches the bootloader (the boot HAL was failing on fake slot links)
- TWRP's slot menu reports a failed switch instead of pretending it worked
- Vibration works again (restored aw8697 haptic firmware)
- /firmware mounts the correct slot; cleaner fstab, twrp.flags and recovery.wipe
- Removed duplicate USB setup that spammed errors in the log

### Added
- lpdump, lptools and bootctl
- "Automatically reflash TWRP after flashing a ROM" works with both install methods

### High-speed flash options (Install screen)
| Option | Default |
| --- | --- |
| High-speed flash | off |
| Verify images after writing | on |
| Allow overwriting the current slot | off (needed on this phone: two ROMs don't fit in super) |
| Also flash firmware | off |

If a zip can't be handled, and nothing has been written yet, the install continues the normal way.

### Installation
```bash
fastboot flash recovery_a twrp_RMX3371.img
fastboot flash recovery_b twrp_RMX3371.img
fastboot reboot recovery
```

### Notes
- Switching between stock realme UI and a custom ROM needs Format Data.
- Every ROM install reuses the current slot's super space; the current slot won't boot until the install finishes.
- Tick "Automatically reflash TWRP after flashing a ROM", since ROM zips replace recovery on the slot they write.
- Copy the zip to internal storage and use Install; it's ~3x faster than adb sideload on this phone's USB 2.0 port.

### Tested
Stock realme UI 14.0.0.2100 (with and without firmware) and an AOSP-based ROM: decrypt, touch, MTP, ADB,
vibration, fastbootd, slot switching, normal and high-speed installs.

### Checksum
`twrp_RMX3371.img` SHA-256:
```
918d26cfd0bc936a6686cfbdedbe358a70cff736d452b3ca705b091daf0ecce0
```

### Credits
- TeamWin, for TWRP
- YOGRaJ, for the original device tree
- Khargosxh18, for the original high-speed flash and the otaripper direct-flash patch
- syedinsaf, for otaripper
