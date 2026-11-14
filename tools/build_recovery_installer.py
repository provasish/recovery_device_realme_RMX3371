#!/usr/bin/env python3
"""Build a reproducible, unsigned TWRP installer for RMX3371's recovery slots."""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import zipfile

PARTITION_SIZE = 134217728
ROOT = Path(__file__).resolve().parents[1]


def validate_image(image):
    if not 1660 <= len(image) <= PARTITION_SIZE:
        raise ValueError("recovery image is truncated or exceeds the 128 MiB partition")
    if image[:8] != b"ANDROID!":
        raise ValueError("expected an Android boot image")
    kernel, ramdisk, second = (struct.unpack_from("<I", image, n)[0] for n in (8, 16, 24))
    page, version = struct.unpack_from("<II", image, 36)
    if version != 2 or page != 4096 or not kernel or not ramdisk:
        raise ValueError("expected this board's v2 image, 4096-byte pages, kernel and ramdisk")
    recovery_dtbo_size = struct.unpack_from("<I", image, 1632)[0]
    header_size = struct.unpack_from("<I", image, 1644)[0]
    dtb_size = struct.unpack_from("<I", image, 1648)[0]
    if header_size != 1660 or not dtb_size:
        raise ValueError("invalid v2 header or missing device tree")
    align = lambda n: (n + page - 1) // page * page
    required = page + sum(align(n) for n in (kernel, ramdisk, second, recovery_dtbo_size, dtb_size))
    if required > len(image):
        raise ValueError("image sections extend beyond the image")


def build(image_path, output):
    image_path, output = Path(image_path), Path(output)
    if image_path.resolve() == output.resolve():
        raise ValueError("output must not replace the input image")
    image = image_path.read_bytes()
    validate_image(image)
    digest = hashlib.sha256(image).hexdigest()
    script = (ROOT / "installer/update-binary").read_text()
    script = script.replace("@IMAGE_SIZE@", str(len(image))).replace("@IMAGE_SHA256@", digest)
    entries = {
        "META-INF/com/google/android/update-binary": (script.encode(), 0o755),
        "META-INF/com/google/android/updater-script": (b"# Installation is performed by update-binary.\n", 0o644),
        "recovery.img": (image, 0o644),
        "recovery.img.sha256": ((digest + "  recovery.img\n").encode(), 0o644),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=output.name + ".", dir=output.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name, (content, mode) in entries.items():
                info = zipfile.ZipInfo(name, (2009, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (0o100000 | mode) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f"Installer: {output} (image SHA-256: {digest})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        build(args.image, args.output)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Installer packaging failed: {error}\n")
