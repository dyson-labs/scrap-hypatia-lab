#!/usr/bin/env bash
set -euo pipefail

# If run as a script, this points at scripts/build_scap_ffi.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT/vendor/tasklib"
cargo build -p scap-ffi --release

echo "Built: $ROOT/vendor/tasklib/target/release/libscap_ffi.so"
