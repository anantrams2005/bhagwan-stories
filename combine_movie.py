#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.audio.ace_step import AceStepMusicGenerator
from src.audio.assembler import MovieAssembler
from src.story import load_story, validate_story


def main() -> int:
    p = argparse.ArgumentParser(description="Generate story music and combine Kaggle I2V clips.")
    p.add_argument("story", type=Path)
    p.add_argument("--movie-dir", type=Path)
    p.add_argument("--music-backend", choices=["none", "ace_step"], default="ace_step")
    p.add_argument("--ace-step-root", type=Path)
    p.add_argument("--ace-step-checkpoints", type=Path)
    p.add_argument("--ace-step-dit-model", default="acestep-v15-turbo")
    p.add_argument("--ace-step-lm-model", default="acestep-5Hz-lm-0.6B")
    p.add_argument("--ace-step-device", default="mps")
    p.add_argument("--ffmpeg", default="ffmpeg")
    args = p.parse_args()

    story = load_story(args.story)
    errors = validate_story(story)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    movie_dir = args.movie_dir or Path(story.get("output_dir", "output")) / story["id"]
    movie_dir.mkdir(parents=True, exist_ok=True)

    music_generator = None
    if args.music_backend == "ace_step":
        root = args.ace_step_root
        if root is None:
            import os
            root_value = os.environ.get("ACE_STEP_ROOT")
            root = Path(root_value) if root_value else None
        if root is None:
            raise SystemExit("--ace-step-root or ACE_STEP_ROOT is required for music generation")
        music_generator = AceStepMusicGenerator(
            root,
            checkpoint_dir=args.ace_step_checkpoints,
            dit_model=args.ace_step_dit_model,
            lm_model=args.ace_step_lm_model,
            device=args.ace_step_device,
        )

    final = MovieAssembler(args.ffmpeg).combine(story, movie_dir, music_generator)
    print(json.dumps({"final": str(final)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
