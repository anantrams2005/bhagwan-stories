from __future__ import annotations

from pathlib import Path
from typing import Any


class SceneImageStage:
    """Compose 16:9 shot source images from up to three reusable asset refs."""

    MAX_REFERENCE_IMAGES = 3

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

                if len(asset_ids) > self.MAX_REFERENCE_IMAGES:
                    raise ValueError(
                        f"{scene['id']}/{shot['id']} uses {len(asset_ids)} assets; "
                        f"Klein 4B scene generation currently supports at most "
                        f"{self.MAX_REFERENCE_IMAGES} reference images"
                    )

                refs = [asset_refs[a] for a in asset_ids if a in asset_refs]
                if len(refs) != len(asset_ids):
                    missing = [a for a in asset_ids if a not in asset_refs]
                    raise ValueError(
                        f"{scene['id']}/{shot['id']} references unresolved assets: {missing}"
                    )

                image = self.generator.generate(
                    shot["image_prompt"],
                    shot.get("negative_prompt", ""),
                    shot_dir,
                    "source.png",
                    reference_images=refs,
                )
                records.append(
                    {
                        "scene_id": scene["id"],
                        "shot_id": shot["id"],
                        "duration": shot["duration"],
                        "image": str(image),
                        "asset_refs": [str(p) for p in refs],
                        "video": None,
                    }
                )
        return records
