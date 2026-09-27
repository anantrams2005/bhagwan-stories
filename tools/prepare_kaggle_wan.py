#!/usr/bin/env python3
"""Prepare a story output directory for Kaggle WAN I2V testing.

This does not generate video. It copies source images and writes a compact
manifest that a Kaggle notebook can consume without running local ComfyUI.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def prepare(story_dir: Path, destination: Path) -> Path:
    story_file = story_dir / "story.json"
    if not story_file.exists():
        raise FileNotFoundError(f"Missing {story_file}")

    story = json.loads(story_file.read_text(encoding="utf-8"))
    destination.mkdir(parents=True, exist_ok=True)

    manifest = {
        "story_id": story["id"],
        "title": story["title"],
        "shots": [],
    }

    for scene in story["scenes"]:
        for shot in scene["shots"]:
            source = story_dir / "scenes" / scene["id"] / shot["id"] / "source.png"
            if not source.exists():
                raise FileNotFoundError(
                    f"Missing scene image: {source}. Generate the scene image first."
                )

            relative_image = Path("scenes") / scene["id"] / shot["id"] / "source.png"
            target = destination / relative_image
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

            manifest["shots"].append(
                {
                    "scene_id": scene["id"],
                    "shot_id": shot["id"],
                    "image": relative_image.as_posix(),
                    "duration": float(shot.get("duration", 3)),
                    "video_model": shot.get("video_model", "wan2.2"),
                    "video_prompt": shot.get("video_prompt", ""),
                }
            )

    manifest_path = destination / "wan_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Prepared {len(manifest['shots'])} shot(s): {destination}")
    print(f"Manifest: {manifest_path}")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare WAN I2V Kaggle handoff")
    parser.add_argument("story_dir", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    prepare(args.story_dir, args.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
