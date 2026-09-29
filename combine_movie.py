#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from src.audio.ace_step import AceStepMusicGenerator
from src.audio.assembler import MovieAssembler
from src.story import load_story, validate_story


def main() -> int:
    p = argparse.ArgumentParser(
        description="Generate story music and combine Kaggle I2V clips."
    )
    p.add_argument("story", type=Path)
    p.add_argument("--movie-dir", type=Path)
    p.add_argument("--music-backend", choices=["none", "ace_step"], default="ace_step")
    p.add_argument(
        "--ace-step-url",
        default=os.environ.get("ACE_STEP_URL", "http://127.0.0.1:8001"),
        help="Running ACE-Step HTTP API URL (default: http://127.0.0.1:8001)",
    )
    p.add_argument("--ace-step-api-key", default=os.environ.get("ACE_STEP_API_KEY"))
    p.add_argument("--ace-step-model", default=None)
    p.add_argument(
        "--ace-step-no-thinking",
        action="store_true",
        help="Do not use ACE-Step's 5Hz LM during generation",
    )
    p.add_argument("--ace-step-timeout", type=float, default=30.0)
    p.add_argument("--ace-step-poll-timeout", type=float, default=1800.0)
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
        music_generator = AceStepMusicGenerator(
            base_url=args.ace_step_url,
            timeout=args.ace_step_timeout,
            poll_timeout=args.ace_step_poll_timeout,
            api_key=args.ace_step_api_key,
            model=args.ace_step_model,
            thinking=not args.ace_step_no_thinking,
        )

    final = MovieAssembler(args.ffmpeg).combine(story, movie_dir, music_generator)
    print(json.dumps({"final": str(final)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
