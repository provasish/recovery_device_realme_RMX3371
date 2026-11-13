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
        # TWRP only ever sets "encrypted", so an unencrypted /data (e.g. right
        # after Format Data) leaves the property unset. FBE keeps its key in
        # /data/unencrypted, which is readable as soon as /data is mounted:
        # if it's there, TWRP just hasn't set the property yet, so keep waiting.
        '') [ ! -e /data/unencrypted/key/version ] || return 1 ;;
        *) return 1 ;;
    esac
}

# Returns 0 when done or /data isn't ready yet, 1 on an error worth retrying
# (e.g. /data unmounted mid-way by Format Data), 2 when something unexpected
# is in the way (symlink, non-file image, foreign link): never touch that.
make_fake_partition() (
    name=$1
    data_ready || exit 0
    cd /data || exit 1
    # Pin the actual filesystem for this short operation. If /data was
    # unmounted between the check and cd, refuse to write to the ramdisk.
    [ "$(stat -c %d .)" != "$(stat -c %d /)" ] || exit 0
    [ ! -L "$name" ] || exit 2
    mkdir -p "$name" || exit 1
    cd "$name" || exit 1
    [ ! -L "$name.img" ] || exit 2
    if [ ! -e "$name.img" ]; then
        (set -C; : > "$name.img") || exit 1
    fi
    [ -f "$name.img" ] || exit 2

    target="/data/$name/$name.img"
    # update_engine looks next to misc (/dev/block/by-name). Do not add
    # synthetic GPT entries to the QTI boot HAL's bootdevice directory.
    for slot in a b; do
        link="/dev/block/by-name/${name}_$slot"
        if [ -e "$link" ] || [ -L "$link" ]; then
            [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ] || exit 2
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
retrying=" "
while sleep 2; do
    for name in "$@"; do
        rc=0
        make_fake_partition "$name" || rc=$?
        case "$rc" in
            0)
                case "$retrying" in
                    *" $name "*) retrying=${retrying%%" $name "*}" "${retrying#*" $name "} ;;
                esac
                ;;
            2)
                echo "make-fake-partitions: unexpected file or link for $name; stopping" >> /tmp/recovery.log
                exit 1
                ;;
            *)
                # Log once per failure streak, not every 2 seconds.
                case "$retrying" in
                    *" $name "*) ;;
                    *)
                        echo "make-fake-partitions: failed for $name; retrying" >> /tmp/recovery.log
                        retrying="$retrying$name "
                        ;;
                esac
                ;;
        esac
    done
done
