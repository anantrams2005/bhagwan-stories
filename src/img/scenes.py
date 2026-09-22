from __future__ import annotations

from pathlib import Path
from typing import Any


class SceneImageStage:
    """Compose 16:9 shot source images with the Klein 4B 3-ref workflow."""

    REQUIRED_REFERENCE_IMAGES = 3

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
        total_shots = sum(len(scene["shots"]) for scene in story["scenes"])
        print(f"[SCENE] Starting {total_shots} shot(s) with FLUX.2 Klein 4B")
        print("[SCENE] Source dimensions are derived by Klein GetImageSize; use 16:9 refs.")
        shot_number = 0
        for scene in story["scenes"]:
            for shot in scene["shots"]:
                shot_number += 1
                print(f"[SCENE] Shot {shot_number}/{total_shots}: {scene['id']}/{shot['id']}")
                shot_dir = movie_dir / "scenes" / scene["id"] / shot["id"]
                asset_ids = shot.get("assets", shot.get("characters", []))

                if len(asset_ids) != self.REQUIRED_REFERENCE_IMAGES:
                    raise ValueError(
                        f"{scene['id']}/{shot['id']} must declare exactly "
                        f"{self.REQUIRED_REFERENCE_IMAGES} assets for the Klein 4B "
                        "scene workflow (reference 1, reference 2, reference 3)"
                    )

                refs = [asset_refs[a] for a in asset_ids]
                print("[SCENE]   refs: " + " | ".join(str(p) for p in refs))
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
        print(f"[SCENE] Completed {len(records)} scene image(s)")
        return records
