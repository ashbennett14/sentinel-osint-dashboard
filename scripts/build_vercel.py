#!/usr/bin/env python3
"""Create Vercel's static public directory from the canonical frontend."""

from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
source = root / "frontend"
destination = root / "public"
if destination.exists():
    shutil.rmtree(destination)
shutil.copytree(source, destination)
