#!/usr/bin/env python3
"""Make the stock realme kernel create f2fs inodes that AOSP kernels can read.

The stock realme UI 14 kernel (4.19.157-perf+) gives every new f2fs inode a
48-byte extra attribute area (i_extra_isize) when the filesystem is larger
than 32 GiB (sbi flag at +0xbac, bit 1). Upstream and AOSP kernels for this
phone only accept up to 36 bytes and fail every access with EUCLEAN
("Structure needs cleaning"). Files and folders TWRP wrote to /data were then
unreadable on AOSP ROMs, and one such entry blanked the whole folder listing.

f2fs_new_inode() does:
    ldr  w8, [x20, #0xbac]
    mov  w9, #0x24
    tst  w8, #0x2
    mov  w8, #0x30        <- patched to mov w8, #0x24
    csel w8, w9, w8, eq
    str  w8, [x19, #0x540] (F2FS_I(inode)->i_extra_isize)

Only inode creation changes. Reading 48-byte inodes (stock realme UI data) is
untouched, and the extra fields are already skipped for 36-byte inodes:
the stock kernel checks each inode's own i_extra_isize before using them,
exactly as it does for inodes the AOSP ROM creates.

usage: patch_f2fs_extra_isize.py prebuilt/Image
"""
import struct
import sys

OFF = 0x40F574
CTX = bytes.fromhex('88ae4bb9' '89048052' '1f011f72')  # ldr w8,[x20,#0xbac]; mov w9,#0x24; tst w8,#2
OLD = struct.pack('<I', 0x52800608)  # mov w8, #0x30
NEW = struct.pack('<I', 0x52800488)  # mov w8, #0x24

path = sys.argv[1]
k = bytearray(open(path, 'rb').read())
if k[OFF - 12:OFF] != CTX:
    sys.exit('unexpected code at %#x: not the kernel this patch was made for' % OFF)
if k[OFF:OFF + 4] == NEW:
    print('already patched')
    sys.exit(0)
if k[OFF:OFF + 4] != OLD or bytes(k).count(CTX + OLD) != 1:
    sys.exit('unexpected instruction at %#x' % OFF)
k[OFF:OFF + 4] = NEW
open(path, 'wb').write(k)
print('patched %s at %#x: mov w8, #0x30 -> mov w8, #0x24' % (path, OFF))
