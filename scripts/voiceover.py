#!/usr/bin/env python
"""Run the StoryVerse voiceover CLI without installing the package."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from storyverse.voiceover import main

if __name__ == "__main__":
    raise SystemExit(main())
