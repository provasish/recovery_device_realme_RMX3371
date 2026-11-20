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

    def test_haptic_flag_is_declared_in_the_fork(self):
        board = board_value("TW_HAPTIC_DEFAULT_MS")
        self.assertIsNotNone(board, "BoardConfig must set TW_HAPTIC_DEFAULT_MS")
        self.assertTrue(board.isdigit())
        mk = Path(__file__).resolve().parents[2] / "bootable" / "recovery" / "Android.mk"
        if mk.is_file():  # only checkable inside a full AOSP checkout
            self.assertIn("TW_HAPTIC_DEFAULT_MS", mk.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
