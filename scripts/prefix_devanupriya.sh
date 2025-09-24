#!/usr/bin/env bash
# Prefix PDF filenames with "Devanupriya " ahead of existing "Shri" names.
# Usage: ./prefix_devanupriya.sh [directory]
# Defaults to the repository's pdfs/ directory when no argument is supplied.

set -euo pipefail

DEFAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/pdfs"
TARGET_DIR="${1:-$DEFAULT_DIR}"

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Directory not found: $TARGET_DIR" >&2
  exit 1
fi

shopt -s nullglob

for filepath in "$TARGET_DIR"/Shri*.pdf; do
  filename="$(basename "$filepath")"

  if [[ "$filename" == Devanupriya* ]]; then
    echo "[skip] $filename already prefixed"
    continue
  fi

  newname="Devanupriya $filename"
  target="$TARGET_DIR/$newname"

  if [[ -e "$target" ]]; then
    echo "[error] Target already exists: $newname" >&2
    continue
  fi

  echo "Renaming $filename -> $newname"
  mv "$filepath" "$target"

done
