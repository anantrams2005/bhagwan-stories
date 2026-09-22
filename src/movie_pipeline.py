from __future__ import annotations

from pathlib import Path
from typing import Any

from src.img.assets import AssetLibrary, AssetStage
from src.img.scenes import SceneImageStage
from src.vid.stage import VideoStage


class MoviePipeline:
    """Production order: assets (Z-Turbo) -> scenes (Klein 4B) -> video."""

    def __init__(
        self,
        asset_image_generator: Any = None,
        scene_image_generator: Any = None,
        video_generator: Any = None,
        asset_root: Path = Path("assets"),
    ) -> None:
        self.assets = AssetStage(
            AssetLibrary(asset_root),
            asset_image_generator,
        )
        self.scene_images = SceneImageStage(scene_image_generator)
        self.video = VideoStage(video_generator) if video_generator else None

    def run(self, story: dict[str, Any], movie_dir: Path) -> list[dict[str, Any]]:
        refs = self.assets.run(story)
        records = self.scene_images.run(story, movie_dir, refs)

        if self.video:
            records = self.video.run(records, story)

        return records
