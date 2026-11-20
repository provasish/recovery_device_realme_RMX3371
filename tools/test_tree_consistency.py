#!/usr/bin/env python3
"""Guard the constants that are duplicated across this tree.

A lot of this device tree's bug history is "same value in two files, one of
them changed". Run this together with the other host tests.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def board_value(name):
    text = (ROOT / "BoardConfig.mk").read_text(encoding="utf-8")
    match = re.search(
        r"^\s*" + re.escape(name) + r"\s*(?:\+=|:=|=)\s*(.*)$", text, re.M
    )
    return match.group(1).strip() if match else None


class TreeConsistencyTests(unittest.TestCase):
    def test_recovery_partition_size_is_identical_everywhere(self):
        board = int(board_value("BOARD_RECOVERYIMAGE_PARTITION_SIZE"))
        packager = re.search(
            r"^PARTITION_SIZE\s*=\s*(\d+)",
            (ROOT / "tools/build_recovery_installer.py").read_text(encoding="utf-8"),
            re.M,
        ).group(1)
        installer = re.search(
            r'^\s*\[ "\$size" = (\d+) \]',
            (ROOT / "installer/update-binary").read_text(encoding="utf-8"),
            re.M,
        ).group(1)
        self.assertEqual(board, int(packager))
        self.assertEqual(board, int(installer))

    def test_installer_aliases_match_board_config(self):
        board = {a.strip() for a in board_value("TARGET_OTA_ASSERT_DEVICE").split(",")}
        script = (ROOT / "installer/update-binary").read_text(encoding="utf-8")
        case = re.search(r"case \"\$device\" in ([^\n]+)\)", script).group(1)
        aliases = {a.strip() for a in case.split("|")}
        self.assertEqual(board, aliases)
        self.assertNotIn("@IMAGE_SIZE@", script.replace("@IMAGE_SIZE@", "", 1))
        self.assertTrue(board)

    def test_referenced_files_exist(self):
        device_path = "device/realme/RMX3371"
        for name in ("TARGET_RECOVERY_FSTAB", "TARGET_RECOVERY_WIPE", "TARGET_SYSTEM_PROP"):
            value = board_value(name).replace("$(DEVICE_PATH)", device_path)
            path = ROOT / value
            if not path.is_file():  # standalone clone: the repo *is* the device dir
                path = ROOT / value.replace(device_path + "/", "", 1)
            self.assertTrue(path.is_file(), f"{name} points to missing {path}")
        for path in (
            "prebuilt/Image", "prebuilt/dtb", "prebuilt/dtbo.img",
            "installer/update-binary", "tools/build_recovery_installer.py",
            "tools/patch_f2fs_extra_isize.py", "tools/test_security_certs.py",
            "recovery/root/system/etc/security/otacerts.zip",
        ):
            self.assertTrue((ROOT / path).is_file(), f"missing {path}")

    # Flags that only exist in the recovery fork; an unknown flag is silently
    # ignored by the build, so check both sides.
    FORK_FLAGS = {
        "TW_HAPTIC_DEFAULT_MS": str.isdigit,
        "TW_SKIP_FBE_DECRYPTION_SDKVERSION": str.isdigit,
        "TW_DEFAULT_REFLASH_TWRP": lambda v: v == "true",
        "TW_REFUSE_ZIPS_AFTER_AB_ROM": lambda v: v == "true",
        "TW_DEFAULT_TIMEZONE_IST": lambda v: v == "true",
    }

    def fork_file(self, relative):
        # tools/ -> RMX3371 -> realme -> device -> AOSP root
        return Path(__file__).resolve().parents[4] / "bootable" / "recovery" / relative

    def test_fork_flags_are_set_and_declared_in_the_fork(self):
        mk = self.fork_file("Android.mk")
        for name, valid in self.FORK_FLAGS.items():
            with self.subTest(flag=name):
                board = board_value(name)
                self.assertIsNotNone(board, f"BoardConfig must set {name}")
                self.assertTrue(valid(board), f"{name} := {board}")
                if mk.is_file():  # only checkable inside a full AOSP checkout
                    self.assertIn(name, mk.read_text(encoding="utf-8"))

    def test_skip_decryption_sdk_is_newer_than_android_12(self):
        self.assertGreater(int(board_value("TW_SKIP_FBE_DECRYPTION_SDKVERSION")), 32)

    def test_display_prop_reaches_the_fork(self):
        props = (ROOT / "system.prop").read_text(encoding="utf-8").splitlines()
        self.assertIn("ro.twrp.drm.prefer_60hz=true", [p.strip() for p in props])
        drm = self.fork_file("minuitwrp/graphics_drm.cpp")
        if drm.is_file():
            self.assertIn("ro.twrp.drm.prefer_60hz", drm.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
