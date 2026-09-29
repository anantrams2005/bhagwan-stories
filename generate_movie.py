#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.img.comfyui import ComfyUIImageGenerator
from src.movie_pipeline import MoviePipeline
from src.story import build_plan, load_story, validate_story
from src.vid.comfyui import ComfyUIVideoGenerator
from src.vid.stage import VideoStage

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_ASSET_WORKFLOW = REPO_ROOT / "workflows" / "z_turbo_assets.json"
DEFAULT_SCENE_WORKFLOW = REPO_ROOT / "workflows" / "flux2_klein_4b_scene.json"
DEFAULT_VIDEO_WORKFLOW = REPO_ROOT / "workflows" / "wan22_i2v_api.json"


def build_existing_video_records(story: dict, movie_dir: Path) -> list[dict]:
    """Build records from already-generated scene images for video-only runs."""
    records = []
    missing = []

    for scene in story["scenes"]:
        for shot in scene["shots"]:
            image = movie_dir / "scenes" / scene["id"] / shot["id"] / "source.png"
            if not image.exists():
                missing.append(f"{scene['id']}/{shot['id']}")
                continue
            records.append(
                {
                    "scene_id": scene["id"],
                    "shot_id": shot["id"],
                    "image": str(image),
                    "duration": float(shot.get("duration", 3)),
                }
            )

    if missing:
        raise SystemExit(
            "Video-only run requires every story shot to have source.png. "
            f"Missing {len(missing)} shot(s): {', '.join(missing)}"
        )

    expected = sum(len(scene["shots"]) for scene in story["scenes"])
    if len(records) != expected:
        raise SystemExit(f"Expected {expected} shots but found {len(records)} scene images.")

    return records


def main() -> int:
    p = argparse.ArgumentParser(description="Generate a cinematic devotional mini-movie.")
    p.add_argument("story", type=Path)
    p.add_argument("--validate", action="store_true")
    p.add_argument("--plan", action="store_true")
    p.add_argument("--video-only", action="store_true",
                   help="Skip asset/scene generation and run I2V for every existing story shot.")
    p.add_argument("--image-backend", choices=["none", "comfyui"], default="none")
    p.add_argument("--asset-image-workflow", type=Path, default=DEFAULT_ASSET_WORKFLOW)
    p.add_argument("--scene-image-workflow", type=Path, default=DEFAULT_SCENE_WORKFLOW)
    p.add_argument("--video-backend", choices=["none", "comfyui_wan"], default="none")
    p.add_argument("--video-workflow", type=Path, default=DEFAULT_VIDEO_WORKFLOW)
    p.add_argument("--comfyui-url", default="http://127.0.0.1:8188")
    p.add_argument("--asset-root", type=Path, default=Path("assets"))
    args = p.parse_args()

    story = load_story(args.story)
    errors = validate_story(story)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    if args.validate:
        print(f"VALID: {story['title']}")
        return 0

    if args.plan:
        print(json.dumps(build_plan(story), ensure_ascii=False, indent=2))
        return 0

    if args.video_only and args.video_backend != "comfyui_wan":
        raise SystemExit("--video-only requires --video-backend comfyui_wan")

    asset_image_gen = None
    scene_image_gen = None
    video_gen = None

    if args.image_backend == "comfyui":
        asset_image_gen = ComfyUIImageGenerator(args.comfyui_url, args.asset_image_workflow)
        scene_image_gen = ComfyUIImageGenerator(args.comfyui_url, args.scene_image_workflow)

    if args.video_backend == "comfyui_wan":
        video_gen = ComfyUIVideoGenerator(args.comfyui_url, args.video_workflow)

    # Scene source images live alongside the story JSON (for example,
    # movies/<story_id>/scenes/), while generated video output follows
    # story.output_dir. Keep these roots separate for video-only runs.
    story_dir = args.story.resolve().parent
    movie_dir = Path(story.get("output_dir", "output")) / story["id"]
    movie_dir.mkdir(parents=True, exist_ok=True)

    if args.video_only:
        records = build_existing_video_records(story, story_dir)
        records = VideoStage(video_gen).run(records, story)
    else:
        pipeline = MoviePipeline(
            asset_image_generator=asset_image_gen,
            scene_image_generator=scene_image_gen,
            video_generator=video_gen,
            asset_root=args.asset_root,
        )
        records = pipeline.run(story, movie_dir)

    manifest = {"story_id": story["id"], "title": story["title"], "shots": records}
    manifest_path = movie_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Movie manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
