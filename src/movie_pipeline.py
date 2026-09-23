from __future__ import annotations

import json
import shutil
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

    @staticmethod
    def _copy_story_assets(refs: dict[str, Path], movie_dir: Path) -> None:
        """Package the exact reusable references needed by this story for Kaggle handoff."""
        for asset_id, source in refs.items():
            destination = movie_dir / "assets" / asset_id / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def run(self, story: dict[str, Any], movie_dir: Path) -> list[dict[str, Any]]:
        movie_dir = Path(movie_dir)
        for path in ("assets", "scenes", "generated_short_videos", "audio/music", "final"):
            (movie_dir / path).mkdir(parents=True, exist_ok=True)

        refs = self.assets.run(story)
        self._copy_story_assets(refs, movie_dir)
        records = self.scene_images.run(story, movie_dir, refs)
        if self.video:
            records = self.video.run(records, story)

        (movie_dir / "story.json").write_text(
            json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return records
