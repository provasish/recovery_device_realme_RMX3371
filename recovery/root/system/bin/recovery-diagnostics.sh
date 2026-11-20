#!/system/bin/sh
# Read-only collection; no partition mounts, slot changes, or uploads.
umask 077
if [ "$#" -ne 1 ] || [ ! -d "$1" ] || [ ! -w "$1" ]; then
    echo "Usage: recovery-diagnostics.sh EXISTING_WRITABLE_DIRECTORY" >&2
    exit 1
fi
case "$1" in /*) ;; *) echo "Destination must be absolute" >&2; exit 1 ;; esac
out=$(mktemp -d "$1/twrp-diagnostics-XXXXXX") || exit 1
status="$out/status.txt"
printf 'TWRP recovery diagnostics\nOptional tools may be unavailable; see exit codes below.\n' > "$status" || exit 1

collect() {
    filename=$1
    shift
    if ! command -v "$1" >/dev/null 2>&1 || ! command -v timeout >/dev/null 2>&1; then
        printf '%s: skipped (tool or timeout unavailable)\n' "$filename" >> "$status"
        return
    fi
    timeout 15 "$@" > "$out/$filename" 2>&1
    printf '%s: exit %s\n' "$filename" "$?" >> "$status"
}

collect kernel.log dmesg
collect logcat.log logcat -d -t 2000
collect super-slot-a.txt lpdump --slot=0
collect super-slot-b.txt lpdump --slot=1
collect current-slot.txt bootctl get-current-slot
collect snapshot-merge.txt bootctl get-snapshot-merge-status

# FBE decryption needs the QSEECom daemon. twrp-common's decrypt rc starts it
# only for encrypted /data (crypto.ready=1) and stops it again once
# twrp.all.users.decrypted=true, so "not running" is only a fault while
# encrypted /data is still waiting for its keys. Read init's service state;
# pidof can't tell "stopped after decryption" from "never started".
qseecomd_bin=/system/bin/qseecomd
qseecomd_state=$(getprop init.svc.qseecomd)
crypto_state=$(getprop ro.crypto.state)
if [ ! -e "$qseecomd_bin" ]; then
    qseecomd_note='missing from this recovery image'
elif [ ! -x "$qseecomd_bin" ]; then
    qseecomd_note='present but not executable; init cannot start it'
elif [ "$qseecomd_state" = running ]; then
    qseecomd_note=running
elif [ "$(getprop twrp.all.users.decrypted)" = true ]; then
    qseecomd_note="${qseecomd_state:-not started}; expected: stopped after all users were decrypted"
elif [ "$crypto_state" != encrypted ]; then
    qseecomd_note="${qseecomd_state:-not started}; not needed (ro.crypto.state=${crypto_state:-unset})"
else
    qseecomd_note="${qseecomd_state:-not started} while /data is still encrypted; FBE keys are unavailable"
fi
printf 'qseecomd: %s\n' "$qseecomd_note" >> "$status"

{
    date -u
    uname -a
    # Deliberately omit serial numbers and a full property dump.
    for key in ro.product.device ro.product.model ro.boot.slot_suffix ro.boot.slot \
               ro.boot.bootreason ro.crypto.state ro.crypto.type twrp.decrypt.done \
               twrp.all.users.decrypted init.svc.qseecomd \
               ro.virtual_ab.enabled ro.virtual_ab.compression.enabled; do
        printf '%s=%s\n' "$key" "$(getprop "$key")"
    done
} > "$out/device.txt" 2>&1
cp /proc/mounts "$out/mounts.txt" 2>> "$status"
cp /proc/partitions "$out/partitions.txt" 2>> "$status"
collect block-links.txt ls -l /dev/block/by-name /dev/block/bootdevice/by-name /dev/block/mapper

mkdir "$out/pstore" || exit 1
for file in /sys/fs/pstore/*; do
    [ -f "$file" ] && [ ! -L "$file" ] || continue
    cp "$file" "$out/pstore/" 2>> "$status"
done
if [ -r /proc/last_kmsg ]; then
    cp /proc/last_kmsg "$out/last_kmsg.log" 2>> "$status"
fi
if ! cp /tmp/recovery.log "$out/recovery.log"; then
    echo "Failed to save recovery.log" >> "$status"
    exit 1
fi
# Everything above was created root-only (umask 077). On internal storage
# Android reaches /data/media as media_rw, so hand the bundle to the
# destination's owner and open it to that owner and group only; otherwise it
# could only be opened or deleted from TWRP. FAT/exFAT (USB OTG) ignore this.
owner=$(stat -c %u:%g "$1" 2>/dev/null) && chown -R "$owner" "$out" 2>/dev/null
chmod -R u=rwX,g=rwX,o= "$out" 2>/dev/null
sync
echo "Diagnostics saved to $out"
