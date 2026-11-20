#!/usr/bin/env python3
"""Verify the shipped kernel still carries the f2fs extra_isize patch."""
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "prebuilt" / "Image"

OFF = 0x40F574
CTX = bytes.fromhex("88ae4bb9" "89048052" "1f011f72")
NEW = struct.pack("<I", 0x52800488)  # mov w8, #0x24


class KernelPatchTests(unittest.TestCase):
    def test_shipped_kernel_is_patched(self):
        data = IMAGE.read_bytes()
        self.assertGreater(len(data), OFF + 4, "kernel image is truncated")
        self.assertEqual(data[OFF - 12:OFF], CTX, "wrong kernel or moved patch site")
        self.assertEqual(
            data[OFF:OFF + 4], NEW,
            "kernel is unpatched: run tools/patch_f2fs_extra_isize.py prebuilt/Image",
        )
        self.assertEqual(data.count(CTX + NEW), 1, "patch site is not unique")


if __name__ == "__main__":
    unittest.main()
