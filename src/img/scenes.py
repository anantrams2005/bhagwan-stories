from __future__ import annotations
from pathlib import Path
from typing import Any


class SceneImageStage:
    """Create shot source images after character references exist."""

    def __init__(self, generator: Any) -> None:
        self.generator = generator

    def run(self, story: dict[str, Any], movie_dir: Path, character_refs: dict[str, Path]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for scene in story["scenes"]:
            for shot in scene["shots"]:
                shot_dir = movie_dir / "scenes" / scene["id"] / shot["id"]
                # Character references are resolved here so a future image adapter can pass them
                # into a reference/IP-adapter workflow without changing the story JSON or CLI.
                refs = [str(character_refs[c]) for c in shot.get("characters", []) if c in character_refs]
                image = self.generator.generate(shot["image_prompt"], shot.get("negative_prompt", ""), shot_dir, "source.png")
                records.append({
                    "scene_id": scene["id"], "shot_id": shot["id"],
                    "duration": shot["duration"], "image": str(image),
                    "character_refs": refs, "video": None,
                })
        return records
