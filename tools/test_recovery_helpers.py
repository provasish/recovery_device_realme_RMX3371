#!/usr/bin/env python3
"""Host fixtures for the recovery scripts; never mount or access phone partitions.

Run: python3 tools/test_recovery_helpers.py
Absolute Android paths are redirected to a temporary filesystem fixture. This
does not validate Android init, real mount/unmount races, or on-device tools.
"""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "recovery/root/system/bin"


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.blocks = self.root / "blocks"
        self.data.mkdir()
        self.blocks.mkdir()
        self.mounts = self.root / "mounts"
        self.mounts.write_text("")
        self.env = dict(os.environ, PATH="/usr/bin:/bin")

    def reserve(self, state="unencrypted", decrypted="", root_device=False):
        script = (SCRIPTS / "make-fake-partitions-service.sh").read_text()
        functions = script.split('[ "$#" -gt 0 ]')[0]
        functions = functions.replace("/proc/mounts", str(self.mounts))
        functions = functions.replace("/dev/block/by-name", str(self.blocks))
        functions = functions.replace("/data", str(self.data))
        # Model distinct filesystem IDs for a mounted userdata filesystem.
        functions += '\nstat() { if [ "$3" = / ]; then echo 1; else echo %s; fi; }\n' % (1 if root_device else 2)
        functions += 'getprop() { case "$1" in ro.crypto.state) echo %s;; twrp.decrypt.done) echo %s;; esac; }\n' % (shlex.quote(state), shlex.quote(decrypted))
        functions += "make_fake_partition reserve\n"
        return subprocess.run(["sh", "-c", functions], env=self.env, capture_output=True)

    def mounted(self, options="rw", kind="f2fs"):
        self.mounts.write_text(f"/dev/block/dm-0 {self.data} {kind} {options} 0 0\n")

    def test_unmounted_readonly_and_locked_do_not_create_files(self):
        for mounted, state, decrypted in [(False, "unencrypted", ""), (True, "encrypted", "false")]:
            if mounted:
                self.mounted()
            self.assertEqual(self.reserve(state, decrypted).returncode, 0)
            self.assertEqual(list(self.data.iterdir()), [])
            self.assertEqual(list(self.blocks.iterdir()), [])
        self.mounted("ro")
        self.assertEqual(self.reserve().returncode, 0)
        self.assertEqual(list(self.data.iterdir()), [])

    def test_decrypted_data_creates_aliases_and_preserves_image(self):
        self.mounted()
        self.assertEqual(self.reserve("encrypted", "true").returncode, 0)
        image = self.data / "reserve/reserve.img"
        image.write_bytes(b"existing OTA contents")
        self.assertEqual(self.reserve("encrypted", "true").returncode, 0)
        self.assertEqual(image.read_bytes(), b"existing OTA contents")
        for slot in "ab":
            self.assertEqual(os.readlink(self.blocks / f"reserve_{slot}"), str(image))

    def test_unset_crypto_state_means_unencrypted_unless_fbe_key_exists(self):
        # TWRP never sets ro.crypto.state=unencrypted; after Format Data it's unset.
        self.mounted()
        key = self.data / "unencrypted/key"
        key.mkdir(parents=True)
        (key / "version").write_text("1\n")
        self.assertEqual(self.reserve(state="").returncode, 0)
        self.assertFalse((self.data / "reserve").exists())
        self.assertEqual(list(self.blocks.iterdir()), [])
        (key / "version").unlink()
        self.assertEqual(self.reserve(state="").returncode, 0)
        image = self.data / "reserve/reserve.img"
        self.assertTrue(image.is_file())
        for slot in "ab":
            self.assertEqual(os.readlink(self.blocks / f"reserve_{slot}"), str(image))

    def test_transient_failure_is_retryable(self):
        # A failed write (here: unwritable link directory) returns 1 so the
        # loop retries, unlike an unexpected file or link, which returns 2.
        if os.geteuid() == 0:
            self.skipTest("root ignores directory permissions")
        self.mounted()
        self.blocks.chmod(0o500)
        self.addCleanup(self.blocks.chmod, 0o700)
        self.assertEqual(self.reserve().returncode, 1)
        self.blocks.chmod(0o700)
        self.assertEqual(self.reserve().returncode, 0)
        self.assertTrue((self.blocks / "reserve_a").is_symlink())

    def run_loop(self, prelude):
        """Run the whole helper, loop included, for a few iterations."""
        script = (SCRIPTS / "make-fake-partitions-service.sh").read_text()
        log = self.root / "recovery.log"
        log.write_text("")
        for before, after in {
            "/proc/mounts": str(self.mounts),
            "/dev/block/by-name": str(self.blocks),
            "/tmp/recovery.log": str(log),
            "/data": str(self.data),
        }.items():
            script = script.replace(before, after)
        counter = self.root / "iterations"
        stubs = (
            'stat() { if [ "$3" = / ]; then echo 1; else echo 2; fi; }\n'
            'getprop() { case "$1" in ro.crypto.state) echo unencrypted;; esac; }\n'
            # Stop after five iterations instead of looping forever.
            'sleep() { n=$(cat %s 2>/dev/null || echo 0); echo $((n + 1)) > %s; [ "$n" -lt 5 ] || exit 0; }\n'
            % (shlex.quote(str(counter)), shlex.quote(str(counter)))
        )
        result = subprocess.run(["sh", "-c", stubs + prelude + script, "sh", "reserve"],
                                env=self.env, capture_output=True)
        return result, log.read_text()

    def test_loop_retries_transient_failures_and_logs_once(self):
        self.mounted()
        calls = self.root / "ln-calls"
        # The first two ln calls fail, as if /dev or /data was briefly unavailable.
        prelude = ('ln() { c=$(cat %s 2>/dev/null || echo 0); echo $((c + 1)) > %s; '
                   '[ "$c" -ge 2 ] || return 1; command ln "$@"; }\n'
                   % (shlex.quote(str(calls)), shlex.quote(str(calls))))
        result, log = self.run_loop(prelude)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log.count("failed for reserve; retrying"), 1)
        self.assertNotIn("stopping", log)
        for slot in "ab":
            self.assertTrue((self.blocks / f"reserve_{slot}").is_symlink())

    def test_loop_stops_on_unexpected_node(self):
        self.mounted()
        (self.blocks / "reserve_a").write_bytes(b"real partition placeholder")
        result, log = self.run_loop("")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(log.count("stopping"), 1)
        self.assertEqual((self.blocks / "reserve_a").read_bytes(), b"real partition placeholder")

    def test_ramdisk_filesystem_is_rejected(self):
        self.mounted()
        self.assertEqual(self.reserve(root_device=True).returncode, 0)
        self.assertEqual(list(self.data.iterdir()), [])

    def test_real_nodes_and_symlink_directories_are_preserved(self):
        self.mounted()
        node = self.blocks / "reserve_a"
        node.write_bytes(b"real partition placeholder")
        self.assertEqual(self.reserve().returncode, 2)
        self.assertFalse(node.is_symlink())
        self.assertEqual(node.read_bytes(), b"real partition placeholder")
        target = self.root / "elsewhere"
        target.mkdir()
        # Use a fresh /data fixture for the symlink attack case.
        (self.data / "reserve/reserve.img").unlink()
        (self.data / "reserve").rmdir()
        (self.data / "reserve").symlink_to(target, target_is_directory=True)
        self.assertEqual(self.reserve().returncode, 2)
        self.assertEqual(list(target.iterdir()), [])

    def test_invalid_partition_name_is_rejected_before_loop(self):
        result = subprocess.run(["sh", str(SCRIPTS / "make-fake-partitions-service.sh"), "../bad"], env=self.env)
        self.assertNotEqual(result.returncode, 0)

    def test_diagnostics_export_with_unusual_path_and_missing_tools(self):
        bindir = self.root / "bin"
        bindir.mkdir()
        for name, body in {
            "getprop": 'echo fixture-value\n',
            "dmesg": 'echo fixture-kernel\n',
            "logcat": 'echo fixture-logcat\n',
            "bootctl": 'echo fixture-bootctl; exit 2\n',
        }.items():
            executable = bindir / name
            executable.write_text("#!/bin/sh\n" + body)
            executable.chmod(0o755)
        self.env["PATH"] = str(bindir) + ":/usr/bin:/bin"
        recovery = self.root / "recovery.log"
        recovery.write_text("fixture recovery log\n")
        pstore = self.root / "pstore"
        pstore.mkdir()
        (pstore / "console-ramoops-0").write_text("fixture crash\n")
        partitions = self.root / "partitions"
        partitions.write_text("fixture partitions\n")
        script = (SCRIPTS / "recovery-diagnostics.sh").read_text()
        for before, after in {
            "/tmp/recovery.log": str(recovery),
            "/proc/mounts": str(self.mounts),
            "/proc/partitions": str(partitions),
            "/proc/last_kmsg": str(self.root / "missing_last_kmsg"),
            "/sys/fs/pstore": str(pstore),
        }.items():
            script = script.replace(before, after)
        runner = self.root / "diagnostics.sh"
        runner.write_text(script)
        dest = self.root / "USB storage's $literal; directory"
        dest.mkdir()
        for _ in range(2):
            result = subprocess.run(["sh", str(runner), str(dest)], env=self.env, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        bundles = list(dest.iterdir())
        self.assertEqual(len(bundles), 2)
        for bundle in bundles:
            self.assertEqual((bundle / "recovery.log").read_bytes(), recovery.read_bytes())
            self.assertEqual((bundle / "pstore/console-ramoops-0").read_text(), "fixture crash\n")
            self.assertIn("skipped", (bundle / "status.txt").read_text())
            self.assertIn("current-slot.txt: exit 2", (bundle / "status.txt").read_text())
            self.assertNotIn("ro.serialno", (bundle / "device.txt").read_text())
            # Owner/group only, so Android's media_rw can open and delete it.
            self.assertEqual(bundle.stat().st_mode & 0o777, 0o770)
            self.assertEqual((bundle / "status.txt").stat().st_mode & 0o777, 0o660)
        result = subprocess.run(["sh", str(runner), str(dest / "missing")], env=self.env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((dest / "missing").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
