#!/usr/bin/env python3
"""Independently verify a built recovery installer ZIP.

Usage: python3 tools/verify_installer.py --zip path/to/twrp-installer.zip
"""
import argparse
import hashlib
import re
import sys
import zipfile

from build_recovery_installer import validate_image

NAMES = {
    "META-INF/com/google/android/update-binary": 0o755,
    "META-INF/com/google/android/updater-script": 0o644,
    "recovery.img": 0o644,
    "recovery.img.sha256": 0o644,
}


def verify(zip_path):
    with zipfile.ZipFile(zip_path) as archive:
        if set(archive.namelist()) != set(NAMES):
            raise ValueError("unexpected ZIP entries: " + ", ".join(sorted(archive.namelist())))
        if archive.testzip() is not None:
            raise ValueError("ZIP contains a corrupt entry")
        for info in archive.infolist():
            mode = (info.external_attr >> 16) & 0o777
            if mode != NAMES[info.filename]:
                raise ValueError(f"bad mode {mode:o} on {info.filename}")

        script = archive.read("META-INF/com/google/android/update-binary").decode("utf-8")
        if "@IMAGE_SIZE@" in script or "@IMAGE_SHA256@" in script:
            raise ValueError("update-binary still contains placeholders")
        size = re.search(r"^IMAGE_SIZE=(\d+)$", script, re.M)
        digest_line = re.search(r"^IMAGE_SHA256=([0-9a-f]{64})$", script, re.M)
        if not size or not digest_line:
            raise ValueError("update-binary has no image size/checksum")

        image = archive.read("recovery.img")
        validate_image(image)
        digest = hashlib.sha256(image).hexdigest()
        if digest != digest_line.group(1):
            raise ValueError("embedded SHA-256 does not match recovery.img")
        if len(image) != int(size.group(1)):
            raise ValueError("embedded image size does not match recovery.img")
        expected = f"{digest}  recovery.img\n".encode()
        if archive.read("recovery.img.sha256") != expected:
            raise ValueError("recovery.img.sha256 does not match recovery.img")
    return f"Installer OK: {len(image)} bytes, SHA-256 {digest}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True)
    args = parser.parse_args()
    try:
        print(verify(args.zip))
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        sys.exit(f"Installer verification failed: {error}")
