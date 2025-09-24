#!/usr/bin/env python3
"""Prefix PDF filenames with 'Devanupriya ' inside the target directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PREFIX = "Devanupriya "


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        nargs="?",
        default=Path(__file__).resolve().parent.parent / "pdfs",
        type=Path,
        help="Directory containing PDFs to rename (default: project pdfs/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned renames without touching the filesystem.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    directory: Path = args.directory

    if not directory.is_dir():
        sys.stderr.write(f"Not a directory: {directory}\n")
        return 1

    pdfs = sorted(directory.glob("*.pdf"))
    if not pdfs:
        print("No PDF files found.")
        return 0

    for pdf in pdfs:
        name = pdf.name
        if name.startswith(PREFIX):
            print(f"[skip] {name} already has prefix")
            continue
        target = pdf.with_name(f"{PREFIX}{name}")
        if target.exists():
            sys.stderr.write(f"[error] Target already exists: {target.name}\n")
            continue
        if args.dry_run:
            print(f"[dry-run] {name} -> {target.name}")
            continue
        pdf.rename(target)
        print(f"Renamed {name} -> {target.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
