#!/usr/bin/env python3
"""Host checks for the OTA keyring shipped in the recovery ramdisk.

TWRP loads every *.x509.pem entry from /system/etc/security/otacerts.zip when
"Zip file signature verification" is enabled. An empty, corrupt or placeholder
keyring silently breaks that setting, so keep a cheap regression check here.
"""
import hashlib
import os
import ssl
import unittest
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYRING = os.path.join(
    REPO, "recovery", "root", "system", "etc", "security", "otacerts.zip"
)
EXPECTED_ENTRIES = {"local_OTA.x509.pem", "special_OTA.x509.pem"}


def read_keyring():
    with zipfile.ZipFile(KEYRING) as archive:
        self_check = archive.testzip()
        if self_check is not None:
            raise AssertionError("corrupt zip entry: " + self_check)
        return {info.filename: archive.read(info) for info in archive.infolist()}


class OtaKeyringTests(unittest.TestCase):
    def test_contains_both_device_certificates(self):
        self.assertEqual(set(read_keyring()), EXPECTED_ENTRIES)

    def test_certificates_are_parseable(self):
        for name, pem in read_keyring().items():
            with self.subTest(entry=name):
                der = ssl.PEM_cert_to_DER_cert(pem.decode("ascii"))
                self.assertEqual(der[0], 0x30)  # ASN.1 SEQUENCE
                self.assertGreater(len(der), 100)

    def test_certificates_are_distinct(self):
        digests = [hashlib.sha256(pem).hexdigest() for pem in read_keyring().values()]
        self.assertEqual(len(digests), len(set(digests)))

    def test_placeholder_certificate_is_gone(self):
        for name, pem in read_keyring().items():
            with self.subTest(entry=name):
                self.assertNotIn(b"OnePlus", pem)
                self.assertNotIn(b"oneplus@", pem)


if __name__ == "__main__":
    unittest.main()
