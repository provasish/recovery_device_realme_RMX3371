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
OTARIPPER_COMMIT="9a01c8ed70f8fc056e18db370dac5dac1bf1fe78"
ZIG_VER="0.13.0"

TREE="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${WORK:-$HOME/otabuild}"
mkdir -p "$WORK"
cd "$WORK"

die() {
  echo "$*" >&2
  exit 1
}

# Compare a downloaded file with a checksum taken from the publisher.
verify_sha256() {
  file="$1"
  expected="$2"
  [ -n "$expected" ] || die "No published checksum for $file"
  actual=$(sha256sum "$file" | cut -d' ' -f1)
  [ "$actual" = "$expected" ] || die "Checksum mismatch for $file: expected $expected, got $actual"
}

# Host Rust is installed from the pinned rustup-init binary, verified against
# the checksum rustup publishes next to it. Older versions piped sh.rustup.rs
# straight into a shell.
if [ ! -x "$HOME/.cargo/bin/rustup" ]; then
  RUSTUP_DIST="https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu"
  curl --proto '=https' --tlsv1.2 -sSf "$RUSTUP_DIST/rustup-init" -o rustup-init
  curl --proto '=https' --tlsv1.2 -sSf "$RUSTUP_DIST/rustup-init.sha256" -o rustup-init.sha256
  verify_sha256 rustup-init "$(cut -d' ' -f1 rustup-init.sha256)"
  chmod +x rustup-init
  ./rustup-init -y --profile minimal --no-modify-path
  rm -f rustup-init rustup-init.sha256
fi
# shellcheck disable=SC1091
. "$HOME/.cargo/env"
rustup toolchain install stable --profile minimal
rustup target add --toolchain stable aarch64-unknown-linux-musl

if [ ! -x "$WORK/zig-linux-x86_64-$ZIG_VER/zig" ]; then
  # Zig publishes the tarball checksum only inside index.json.
  zig_sha=$(curl -sSfL https://ziglang.org/download/index.json | awk -v ver="$ZIG_VER" '
    index($0, "\"" ver "\": {") { in_ver = 1; next }
    in_ver && /"x86_64-linux": \{/ { in_arch = 1; next }
    in_ver && in_arch && /"shasum":/ {
      match($0, /"[0-9a-f]{64}"/)
      print substr($0, RSTART + 1, RLENGTH - 2)
      exit
    }')
  [ -n "$zig_sha" ] || die "Could not read the published Zig $ZIG_VER checksum"
  curl -sSfL "https://ziglang.org/download/$ZIG_VER/zig-linux-x86_64-$ZIG_VER.tar.xz" -o zig.tar.xz
  verify_sha256 zig.tar.xz "$zig_sha"
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
# The full commit id above is the pin; refuse a tree that does not match it.
[ "$(git rev-parse HEAD)" = "$OTARIPPER_COMMIT" ] || die "otaripper is not at $OTARIPPER_COMMIT"
git log --oneline -1

MODE=musl CPU=v82 LTO=fat FEATURES=lite bash ./build.sh

OUT="target/aarch64-unknown-linux-musl/release/otaripper"
install -m 0755 "$OUT" "$TREE/recovery/root/system/bin/otaripper"
sha256sum "$TREE/recovery/root/system/bin/otaripper"
echo "Copied to recovery/root/system/bin/otaripper"
