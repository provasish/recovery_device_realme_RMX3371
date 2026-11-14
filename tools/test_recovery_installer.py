#!/usr/bin/env python3
"""Host fixtures only: no real block devices are opened or written."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("packager", ROOT / "tools/build_recovery_installer.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


def image_bytes():
    image = bytearray(16384)
    image[:8] = b"ANDROID!"
    for offset, value in ((8, 32), (16, 32), (36, 4096), (40, 2), (1644, 1660), (1648, 32)):
        struct.pack_into("<I", image, offset, value)
    return bytes(image)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / "recovery.img"
        self.image.write_bytes(image_bytes())
        self.zip = self.root / "installer.zip"
        with contextlib.redirect_stdout(io.StringIO()):
            packager.build(self.image, self.zip)

    def test_reproducible_archive_and_permissions(self):
        before = self.zip.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            packager.build(self.image, self.zip)
        self.assertEqual(before, self.zip.read_bytes())
        with zipfile.ZipFile(self.zip) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read("recovery.img"), image_bytes())
            script = archive.getinfo("META-INF/com/google/android/update-binary")
            self.assertEqual((script.external_attr >> 16) & 0o777, 0o755)
            self.assertNotIn(b"@IMAGE_", archive.read(script))

    def test_invalid_images_preserve_previous_output(self):
        previous = self.zip.read_bytes()
        for offset, value in ((0, 0), (40, 3), (36, 2048), (8, 0), (16, 0), (1644, 0), (1648, 0), (8, 9999999)):
            image = bytearray(image_bytes())
            struct.pack_into("<I", image, offset, value)
            self.image.write_bytes(image)
            with self.assertRaises(ValueError):
                packager.build(self.image, self.zip)
            self.assertEqual(previous, self.zip.read_bytes())
        with self.assertRaises(ValueError):
            packager.validate_image(b"ANDROID!")

    def run_installer(self, slot="_a", device="RMX3371", fail="", missing=False, bad_hash=False, alias=False):
        bins = self.root / "bin"
        bins.mkdir()
        blocks = self.root / "blocks"
        blocks.mkdir()
        for name in ("recovery_a", "recovery_b"):
            (blocks / name).write_bytes(b"unchanged")
        if missing:
            (blocks / "recovery_b").unlink()
        log = self.root / "writes"
        scripts = {
            "getprop": 'case "$1" in ro.boot.slot_suffix) echo "$SLOT";; *) echo "$DEVICE";; esac',
            "blockdev": 'case "$FAIL:$2" in small:*recovery_b) echo 1;; *) echo 134217728;; esac',
            "stat": 'if [ "$ALIAS" = yes ]; then echo same; else echo "$3"; fi',
            "sync": 'exit 0',
            "dd": '''echo "$*" >> "$WRITES"
case "$FAIL" in write) exit 1;; esac
/bin/dd "$@" || exit 1
if [ "$FAIL" = verify ]; then
  for arg in "$@"; do case "$arg" in of=*) printf corrupt > "${arg#of=}";; esac; done
fi''',
        }
        for name, body in scripts.items():
            path = bins / name
            path.write_text("#!/bin/sh\n" + body + "\n")
            path.chmod(0o755)
        with zipfile.ZipFile(self.zip) as archive:
            script = archive.read("META-INF/com/google/android/update-binary").decode()
        # Only replace block-device identity/paths for ordinary-file fixtures.
        # The real installer has no test mode and always requires block devices.
        script = script.replace('/dev/block/by-name/', str(blocks) + '/')
        script = script.replace('[ -b "$target" ]', '[ -f "$target" ]')
        script = script.replace('/tmp/twrp-installer.', str(self.root / 'work.'))
        if bad_hash:
            script = script.replace('IMAGE_SHA256=', 'IMAGE_SHA256=bad')
        runner = self.root / "run.sh"
        runner.write_text(script)
        env = dict(os.environ, PATH=str(bins) + ":" + os.environ["PATH"], SLOT=slot,
                   DEVICE=device, FAIL=fail, WRITES=str(log), ALIAS="yes" if alias else "no")
        result = subprocess.run(["/bin/sh", str(runner), "3", "1", str(self.zip)],
                                env=env, capture_output=True, text=True, timeout=10)
        writes = log.read_text().splitlines() if log.exists() else []
        self.assertFalse(list(self.root.glob("work.*")), "temporary extraction must be removed")
        return result, writes, blocks

    def test_both_slots_verified_inactive_first(self):
        result, writes, blocks = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("recovery_b", writes[0])
        self.assertIn("recovery_a", writes[1])
        for path in blocks.iterdir():
            self.assertEqual(path.read_bytes(), image_bytes())

    def test_booted_b_writes_a_first(self):
        result, writes, _ = self.run_installer(slot="_b")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("recovery_a", writes[0])

    def assert_no_writes(self, **kwargs):
        result, writes, blocks = self.run_installer(**kwargs)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(writes, [])
        for path in blocks.iterdir():
            self.assertEqual(path.read_bytes(), b"unchanged")

    def test_wrong_device(self):
        self.assert_no_writes(device="RMX33710")

    def test_unknown_slot(self):
        self.assert_no_writes(slot="")

    def test_missing_second_partition(self):
        self.assert_no_writes(slot="_b", missing=True)

    def test_small_second_partition(self):
        self.assert_no_writes(slot="_b", fail="small")

    def test_corrupt_image(self):
        self.assert_no_writes(bad_hash=True)

    def test_aliased_device_ids(self):
        self.assert_no_writes(alias=True)

    def test_write_failure_preserves_other_slot(self):
        result, writes, blocks = self.run_installer(fail="write")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(writes), 1)
        self.assertEqual((blocks / "recovery_a").read_bytes(), b"unchanged")

    def test_readback_failure_preserves_other_slot(self):
        result, writes, blocks = self.run_installer(fail="verify")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(writes), 1)
        self.assertEqual((blocks / "recovery_a").read_bytes(), b"unchanged")

    def test_make_hook_builds_and_refreshes_zip(self):
        build_root = self.root / "build"
        device = build_root / "device/realme/RMX3371"
        device.parent.mkdir(parents=True)
        device.symlink_to(ROOT, target_is_directory=True)
        product = build_root / "out/product"
        product.mkdir(parents=True)
        image = product / "recovery.img"
        image.write_bytes(image_bytes())
        makefile = build_root / "Makefile"
        makefile.write_text('PRODUCT_OUT := out/product\ninclude device/realme/RMX3371/installer/installer.mk\n')
        for target in ("recoveryimage", "recoveryzip"):
            subprocess.run(["make", target], cwd=build_root, check=True, capture_output=True)
        output = product / "twrp-installer-RMX3371.zip"
        previous = output.read_bytes()
        changed = bytearray(image_bytes())
        changed[4096] = 42
        image.write_bytes(changed)
        # Force a newer input even on filesystems with coarse timestamps.
        stamp = output.stat().st_mtime + 2
        os.utime(image, (stamp, stamp))
        subprocess.run(["make", "recoveryimage"], cwd=build_root, check=True, capture_output=True)
        self.assertNotEqual(previous, output.read_bytes())


if __name__ == "__main__":
    unittest.main()
