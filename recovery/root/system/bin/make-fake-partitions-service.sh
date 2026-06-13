#!/system/bin/sh

LOG=/tmp/recovery.log

# Resolve real block device, handles bootdevice and platform paths
get_real_block() {
    local name="$1"
    for path in \
        /dev/block/bootdevice/by-name/$name \
        /dev/block/by-name/$name \
        /dev/block/platform/*/by-name/$name; do
        [ -b "$path" ] && echo "$path" && return 0
    done
    return 1
}

make_fake_partition() {
    local name="$1"
    local real
    real=$(get_real_block "$name")
    if [ $? -ne 0 ]; then
        echo "$(date): ERROR: No real block device found for $name" >> $LOG
        return 1
    fi
    ln -sf "$real" /dev/block/by-name/${name}_a
    ln -sf "$real" /dev/block/by-name/${name}_b
    ln -sf "$real" /dev/block/bootdevice/by-name/${name}_a
    ln -sf "$real" /dev/block/bootdevice/by-name/${name}_b
    echo "$(date): Linked ${name}_a/_b -> $real" >> $LOG
}

if [ $# -eq 0 ]; then
    set -- oplusstanvbk
fi

echo "$(date): Starting fake-partition service for: $*" >> $LOG

# Run once immediately before the loop to avoid race condition on startup
for name in "$@"; do
    make_fake_partition "$name"
done

while sleep 1; do
    for name in "$@"; do
        make_fake_partition "$name"
    done
done
