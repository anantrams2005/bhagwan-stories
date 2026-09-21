#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from src.story import load_story, validate_story, build_plan
from src.image_gen import ComfyUIImageGenerator
from src.video_gen import ComfyUIVideoGenerator

def main() -> int:
    p = argparse.ArgumentParser(description="Generate a cinematic devotional mini-movie.")
    p.add_argument("story", type=Path)
    p.add_argument("--validate", action="store_true")
    p.add_argument("--plan", action="store_true")
    p.add_argument("--image-backend", choices=["none", "comfyui"], default="none")
    p.add_argument("--comfyui-url", default="http://127.0.0.1:8188")
    p.add_argument("--image-workflow", type=Path)
    p.add_argument("--video-backend", choices=["none", "comfyui_wan"], default="none")
    p.add_argument("--video-workflow", type=Path)
    args = p.parse_args()
    story = load_story(args.story)
    errors = validate_story(story)
    if errors:
        for e in errors: print(f"ERROR: {e}")
        return 1
    if args.validate:
        print(f"VALID: {story['title']}")
        return 0
    if args.plan:
        print(json.dumps(build_plan(story), ensure_ascii=False, indent=2))
        return 0

    movie_dir = Path(story.get("output_dir", "movies")) / story["id"]
    movie_dir.mkdir(parents=True, exist_ok=True)
    image_gen = None
    video_gen = None
    if args.image_backend == "comfyui":
        if not args.image_workflow: raise SystemExit("--image-workflow is required")
        image_gen = ComfyUIImageGenerator(args.comfyui_url, args.image_workflow)
    if args.video_backend == "comfyui_wan":
        if not args.video_workflow: raise SystemExit("--video-workflow is required")
        video_gen = ComfyUIVideoGenerator(args.comfyui_url, args.video_workflow)

    manifest = {"story_id": story["id"], "title": story["title"], "shots": []}
    for scene in story["scenes"]:
        for shot in scene["shots"]:
            shot_dir = movie_dir / "scenes" / scene["id"] / shot["id"]
            shot_dir.mkdir(parents=True, exist_ok=True)
            record = {"scene_id": scene["id"], "shot_id": shot["id"], "duration": shot["duration"], "image": None, "video": None}
            if image_gen:
                record["image"] = str(image_gen.generate(shot["image_prompt"], shot.get("negative_prompt", ""), shot_dir, "source.png"))
            if video_gen and record["image"]:
                record["video"] = str(video_gen.generate(Path(record["image"]), shot.get("video_prompt", ""), shot["duration"], shot_dir, "shot.mp4"))
            manifest["shots"].append(record)
    (movie_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Movie manifest: {movie_dir / 'manifest.json'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
