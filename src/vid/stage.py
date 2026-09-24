from __future__ import annotations

from pathlib import Path
from typing import Any


class VideoStage:
    """Generate I2V clips and keep a copy in the story's Kaggle handoff folder."""

    def __init__(self, generator: Any) -> None:
        self.generator = generator

    def run(self, records: list[dict[str, Any]], story: dict[str, Any]) -> list[dict[str, Any]]:
        for record in records:
            shot = next(
                shot for scene in story["scenes"] if scene["id"] == record["scene_id"]
                for shot in scene["shots"] if shot["id"] == record["shot_id"]
            )
            if shot.get("video_model", "wan2.2") != "wan2.2":
                raise ValueError(f"{record['scene_id']}/{record['shot_id']} video_model must be wan2.2")
            shot_dir = Path(record["image"]).parent
            video = self.generator.generate(
                image=Path(record["image"]),
                prompt=shot.get("video_prompt", ""),
                duration=float(record["duration"]),
                output_dir=shot_dir,
                filename="shot.mp4",
            )
            handoff_dir = Path(story.get("output_dir", "output")) / story["id"] / "generated_short_videos" / record["scene_id"]
            handoff_dir.mkdir(parents=True, exist_ok=True)
            handoff = handoff_dir / f"{record['shot_id']}.mp4"
            handoff.write_bytes(video.read_bytes())
            record["video"] = str(video)
            record["handoff_video"] = str(handoff)
        return records
