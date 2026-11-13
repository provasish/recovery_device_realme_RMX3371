#!/system/bin/sh
# Stock OTA reserve images live on userdata, not in the recovery ramdisk.
# Keep the loop outside /data so it does not hold the mount busy while idle.
umask 077

data_ready() {
    awk '$2 == "/data" && ($3 == "f2fs" || $3 == "ext4") &&
         $4 ~ /(^|,)rw(,|$)/ { found=1 } END { exit !found }' /proc/mounts || return 1
    case "$(getprop ro.crypto.state)" in
        unencrypted) ;;
        encrypted) [ "$(getprop twrp.decrypt.done)" = true ] || return 1 ;;
        *) return 1 ;;
    esac
}

make_fake_partition() (
    name=$1
    data_ready || exit 0
    cd /data || exit 1
    # Pin the actual filesystem for this short operation. If /data was
    # unmounted between the check and cd, refuse to write to the ramdisk.
    [ "$(stat -c %d .)" != "$(stat -c %d /)" ] || exit 0
    [ ! -L "$name" ] || exit 1
    mkdir -p "$name" || exit 1
    cd "$name" || exit 1
    [ ! -L "$name.img" ] || exit 1
    if [ ! -e "$name.img" ]; then
        (set -C; : > "$name.img") || exit 1
    fi
    [ -f "$name.img" ] || exit 1

    target="/data/$name/$name.img"
    # update_engine looks next to misc (/dev/block/by-name). Do not add
    # synthetic GPT entries to the QTI boot HAL's bootdevice directory.
    for slot in a b; do
        link="/dev/block/by-name/${name}_$slot"
        if [ -e "$link" ] || [ -L "$link" ]; then
            [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ] || exit 1
        else
            ln -s "$target" "$link" || exit 1
        fi
    done
)

[ "$#" -gt 0 ] || exit 1
for name in "$@"; do
    case "$name" in
        ''|*[!a-zA-Z0-9_]*|.|..) exit 1 ;;
    esac
done

echo "make-fake-partitions: waiting for mounted, decrypted userdata" >> /tmp/recovery.log
while sleep 2; do
    for name in "$@"; do
        if ! make_fake_partition "$name"; then
            echo "make-fake-partitions: failed for $name; stopping" >> /tmp/recovery.log
            exit 1
        fi
    done
done

