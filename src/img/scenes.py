from __future__ import annotations

import re
from pathlib import Path
from typing import Any


SCENE_MODELS: dict[str, dict[str, Any]] = {
    "qwen": {
        "image_model": "qwen_image_edit_2511",
        "label": "Qwen-Image-Edit-2511",
        "min_refs": 1,
        "max_refs": 3,
        "picture_labels": True,
    },
    "flux": {
        "image_model": "flux2_klein_4b",
        "label": "FLUX.2 Klein 4B",
        "min_refs": 3,
        "max_refs": 3,
        "picture_labels": False,
    },
}


class SceneImageStage:
    """Compose 16:9 shot source images with the selected scene model (qwen or flux)."""

    def __init__(self, generator: Any, model: str = "qwen") -> None:
        if model not in SCENE_MODELS:
            raise ValueError(f"scene model must be one of {list(SCENE_MODELS)}; got {model!r}")
        self.generator = generator
        self.model = model
        self.cfg = SCENE_MODELS[model]

    @staticmethod
    def _with_picture_labels(
        prompt: str, asset_ids: list[str], labels: dict[str, str]
    ) -> str:
        """Prefix 'Picture N is <label>.' built from the shot's real asset order,
        so the numbering can never disagree with the references actually sent.
        Prompts that already declare their own Reference/Picture mapping are left as-is.
        """
        if re.search(r"\b(Reference|Picture) 1\b", prompt):
            return prompt
        parts = [
            f"Picture {i} is {labels.get(a, a.replace('_', ' '))}"
            for i, a in enumerate(asset_ids, 1)
        ]
        return "; ".join(parts) + ". " + prompt

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
        label = self.cfg["label"]
        print(f"[SCENE] Starting {total_shots} shot(s) with {label} (--scene-model {self.model})")
        print(f"[SCENE] Model contract: image_prompt -> {label}; video_prompt -> WAN 2.2 only")

        shot_number = 0
        for scene in story["scenes"]:
            for shot in scene["shots"]:
                shot_number += 1
                shot_name = f"{scene['id']}/{shot['id']}"
                shot_dir = movie_dir / "scenes" / scene["id"] / shot["id"]
                destination = shot_dir / "source.png"

                print(f"[SCENE] Shot {shot_number}/{total_shots}: {shot_name}")
                if destination.exists():
                    print("[SCENE]   existing source.png found; skipping generation to preserve approved image.")
                    records.append(
                        {
                            "scene_id": scene["id"],
                            "shot_id": shot["id"],
                            "duration": shot["duration"],
                            "image": str(destination),
                            "asset_refs": [],
                            "video_model": shot.get("video_model", "wan2.2"),
                            "video_prompt": shot.get("video_prompt", ""),
                            "video": None,
                        }
                    )
                    continue

                asset_ids = shot.get("assets", shot.get("characters", []))
                min_refs, max_refs = self.cfg["min_refs"], self.cfg["max_refs"]
                if not min_refs <= len(asset_ids) <= max_refs:
                    need = str(max_refs) if min_refs == max_refs else f"{min_refs} to {max_refs}"
                    raise ValueError(
                        f"{shot_name} must declare {need} assets for the {label} "
                        f"scene workflow (--scene-model {self.model}); got {len(asset_ids)}"
                    )

                refs = [asset_refs[a] for a in asset_ids]
                print("[SCENE]   refs: " + " | ".join(str(p) for p in refs))

                known = {c["image_model"] for c in SCENE_MODELS.values()}
                if shot.get("image_model", self.cfg["image_model"]) not in known:
                    raise ValueError(f"{shot_name} image_model must be one of {sorted(known)}")

                prompt = shot["image_prompt"]
                if self.cfg["picture_labels"]:
                    prompt = self._with_picture_labels(
                        prompt, asset_ids, story.get("reference_labels", {})
                    )
                image = self.generator.generate(
                    prompt,
                    shot.get("negative_prompt", ""),
                    shot_dir,
                    "source.png",
                    reference_images=refs,
                )

                print(f"[SCENE]   completed: {image}")
                records.append(
                    {
                        "scene_id": scene["id"],
                        "shot_id": shot["id"],
                        "duration": shot["duration"],
                        "image": str(image),
                        "asset_refs": [str(p) for p in refs],
                        "video_model": shot.get("video_model", "wan2.2"),
                        "video_prompt": shot.get("video_prompt", ""),
                        "video": None,
                    }
                )

        print(f"[SCENE] Completed {len(records)}/{total_shots} scene image(s)")
        return records
