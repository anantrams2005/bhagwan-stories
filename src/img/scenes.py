from __future__ import annotations

from pathlib import Path
from typing import Any


class SceneImageStage:
    """Compose each shot from the story prompt plus resolved visual assets."""

    def __init__(self, generator: Any) -> None:
        self.generator = generator

    def run(
        self,
        story: dict[str, Any],
        movie_dir: Path,
        asset_refs: dict[str, Path],
    ) -> list[dict[str, Any]]:
        if self.generator is None:
            raise RuntimeError("Scene image generation requested without an image generator")

        records: list[dict[str, Any]] = []
        for scene in story["scenes"]:
            for shot in scene["shots"]:
                shot_dir = movie_dir / "scenes" / scene["id"] / shot["id"]
                asset_ids = shot.get("assets", shot.get("characters", []))
                refs = [str(asset_refs[a]) for a in asset_ids if a in asset_refs]

                prompt = shot["image_prompt"]
                if refs:
                    prompt = (
                        f"{prompt}\n\nVISUAL REFERENCE ASSETS:\n"
                        + "\n".join(refs)
                    )

                image = self.generator.generate(
                    prompt,
                    shot.get("negative_prompt", ""),
                    shot_dir,
                    "source.png",
                )
                records.append({
                    "scene_id": scene["id"],
                    "shot_id": shot["id"],
                    "duration": shot["duration"],
                    "image": str(image),
                    "asset_refs": refs,
                    "video": None,
                })
        return records
