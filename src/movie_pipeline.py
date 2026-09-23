from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.img.assets import AssetLibrary, AssetStage
from src.img.scenes import SceneImageStage
from src.vid.stage import VideoStage


class MoviePipeline:
    """Production order: assets -> scenes -> optional local I2V."""

    def __init__(self, asset_image_generator: Any = None, scene_image_generator: Any = None,
                 video_generator: Any = None, asset_root: Path = Path("assets")) -> None:
        self.assets = AssetStage(AssetLibrary(asset_root), asset_image_generator)
        self.scene_images = SceneImageStage(scene_image_generator)
        self.video = VideoStage(video_generator) if video_generator else None

    def run(self, story: dict[str, Any], movie_dir: Path) -> list[dict[str, Any]]:
        movie_dir = Path(movie_dir)
        (movie_dir / "scenes").mkdir(parents=True, exist_ok=True)
        (movie_dir / "generated_short_videos").mkdir(parents=True, exist_ok=True)
        (movie_dir / "audio" / "music").mkdir(parents=True, exist_ok=True)
        (movie_dir / "final").mkdir(parents=True, exist_ok=True)

        refs = self.assets.run(story)
        records = self.scene_images.run(story, movie_dir, refs)
        if self.video:
            records = self.video.run(records, story)

        (movie_dir / "story.json").write_text(
            json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return records
