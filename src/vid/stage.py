from __future__ import annotations

from pathlib import Path
from typing import Any


class VideoStage:
    """Generate I2V clips from already-composed scene images."""

    def __init__(self, generator: Any) -> None:
        self.generator = generator

    def run(self, records: list[dict[str, Any]], story: dict[str, Any]) -> list[dict[str, Any]]:
        shot_map = {
            (scene["id"], shot["id"]): shot
            for scene in story["scenes"]
            for shot in scene["shots"]
        }

        for record in records:
            shot = shot_map[(record["scene_id"], record["shot_id"])]
            shot_dir = Path(record["image"]).parent
            video = self.generator.generate(
                image=Path(record["image"]),
                prompt=shot.get("video_prompt", ""),
                duration=float(record["duration"]),
                output_dir=shot_dir,
                filename="shot.mp4",
            )
            record["video"] = str(video)

        return records
