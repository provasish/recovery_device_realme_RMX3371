#!/usr/bin/env bash
#
# Rebuild recovery/root/system/bin/otaripper (used by high-speed flash) from source.
#
# Needs an x86_64 Linux host (a build server or WSL) with curl and git. Rust and
# zig are installed into $WORK only; nothing system-wide, no sudo.
#
#   tools/build_otaripper.sh            # build, then copy into the tree
#   WORK=/tmp/ota tools/build_otaripper.sh
#
# Source: the direct-flash fork of otaripper, pinned to the commit the shipped
# binary was built from. Profile: static musl, ARMv8.2-A + dotprod/fp16/crypto,
# which matches the SD870 (Kryo 585).
set -euo pipefail

OTARIPPER_REPO="https://github.com/khargosxh18/otaripper"
OTARIPPER_COMMIT="9a01c8e"
ZIG_VER="0.13.0"

TREE="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${WORK:-$HOME/otabuild}"
mkdir -p "$WORK"
cd "$WORK"

if [ ! -x "$HOME/.cargo/bin/rustup" ]; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
fi
# shellcheck disable=SC1091
. "$HOME/.cargo/env"
rustup toolchain install stable --profile minimal
rustup target add --toolchain stable aarch64-unknown-linux-musl

if [ ! -x "$WORK/zig-linux-x86_64-$ZIG_VER/zig" ]; then
  curl -sSfL "https://ziglang.org/download/$ZIG_VER/zig-linux-x86_64-$ZIG_VER.tar.xz" -o zig.tar.xz
  tar -xf zig.tar.xz
  rm zig.tar.xz
fi
export PATH="$WORK/zig-linux-x86_64-$ZIG_VER:$PATH"

command -v cargo-zigbuild >/dev/null || cargo install --locked cargo-zigbuild

if [ ! -d otaripper ]; then
  git clone "$OTARIPPER_REPO" otaripper
fi
cd otaripper
git fetch --quiet origin
git checkout --quiet "$OTARIPPER_COMMIT"
git log --oneline -1

MODE=musl CPU=v82 LTO=fat FEATURES=lite bash ./build.sh

OUT="target/aarch64-unknown-linux-musl/release/otaripper"
install -m 0755 "$OUT" "$TREE/recovery/root/system/bin/otaripper"
sha256sum "$TREE/recovery/root/system/bin/otaripper"
echo "Copied to recovery/root/system/bin/otaripper"
