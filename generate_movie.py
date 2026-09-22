#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.img.comfyui import ComfyUIImageGenerator
from src.movie_pipeline import MoviePipeline
from src.story import build_plan, load_story, validate_story
from src.vid.comfyui import ComfyUIVideoGenerator

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_ASSET_WORKFLOW = REPO_ROOT / "workflows" / "z_turbo_assets.json"
DEFAULT_SCENE_WORKFLOW = REPO_ROOT / "workflows" / "flux2_klein_4b_scene.json"


def main() -> int:
    p = argparse.ArgumentParser(description="Generate a cinematic devotional mini-movie.")
    p.add_argument("story", type=Path)
    p.add_argument("--validate", action="store_true")
    p.add_argument("--plan", action="store_true")
    p.add_argument("--image-backend", choices=["none", "comfyui"], default="none")
    p.add_argument("--asset-image-workflow", type=Path, default=DEFAULT_ASSET_WORKFLOW)
    p.add_argument("--scene-image-workflow", type=Path, default=DEFAULT_SCENE_WORKFLOW)
    p.add_argument("--video-backend", choices=["none", "comfyui_wan"], default="none")
    p.add_argument("--video-workflow", type=Path)
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

    asset_image_gen = None
    scene_image_gen = None
    video_gen = None

    if args.image_backend == "comfyui":
        asset_image_gen = ComfyUIImageGenerator(
            args.comfyui_url,
            args.asset_image_workflow,
        )
        scene_image_gen = ComfyUIImageGenerator(
            args.comfyui_url,
            args.scene_image_workflow,
        )

    if args.video_backend == "comfyui_wan":
        if not args.video_workflow:
            raise SystemExit("--video-workflow is required")
        video_gen = ComfyUIVideoGenerator(args.comfyui_url, args.video_workflow)

    movie_dir = Path(story.get("output_dir", "movies")) / story["id"]
    movie_dir.mkdir(parents=True, exist_ok=True)

    pipeline = MoviePipeline(
        asset_image_generator=asset_image_gen,
        scene_image_generator=scene_image_gen,
        video_generator=video_gen,
        asset_root=args.asset_root,
    )
    records = pipeline.run(story, movie_dir)

    manifest = {
        "story_id": story["id"],
        "title": story["title"],
        "shots": records,
    }
    manifest_path = movie_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Movie manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
