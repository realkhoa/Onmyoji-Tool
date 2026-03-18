#!/usr/bin/env python3
"""Simple utility to convert all .dds files in a directory to .png
and delete the original .dds files.

Usage:
    python converter.py [path]

If no path is given the default is the "images/masking" folder
in the project root.
"""

import os
import sys
from pathlib import Path

import imageio


def convert_folder(folder: Path) -> None:
    """Convert all .dds files in `folder` to .png and delete originals."""
    if not folder.is_dir():
        print(f"{folder} is not a directory.")
        return

    for item in folder.iterdir():
        if item.suffix.lower() != ".dds":
            continue

        try:
            img = imageio.imread(item)
        except Exception as e:
            print(f"failed to read {item}: {e}")
            continue

        out_path = item.with_suffix(".png")
        try:
            imageio.imwrite(out_path, img)
            print(f"wrote {out_path}")
        except Exception as e:
            print(f"failed to write {out_path}: {e}")
            continue

        try:
            item.unlink()
            print(f"removed {item}")
        except Exception as e:
            print(f"could not remove {item}: {e}")


def main() -> None:
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    else:
        # default relative to script file
        target = Path(__file__).parent.parent / "images" / "masking"

    convert_folder(target)


if __name__ == "__main__":
    main()
