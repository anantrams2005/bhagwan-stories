from __future__ import annotations

import queue
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        """generator: one image generator, or a list of them (one per ComfyUI server).

        With model "qwen" and more than one generator, shots run in parallel,
        one worker per generator. Every other case runs shots sequentially on
        the first generator.
        """
        if model not in SCENE_MODELS:
            raise ValueError(f"scene model must be one of {list(SCENE_MODELS)}; got {model!r}")
        if generator is None:
            self.generators: list[Any] = []
        elif isinstance(generator, (list, tuple)):
            self.generators = list(generator)
        else:
            self.generators = [generator]
        self.generator = self.generators[0] if self.generators else None
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

    @staticmethod
    def _record(scene: dict, shot: dict, image: Any, refs: list[Path]) -> dict[str, Any]:
        return {
            "scene_id": scene["id"],
            "shot_id": shot["id"],
            "duration": shot["duration"],
            "image": str(image),
            "asset_refs": [str(p) for p in refs],
            "video_model": shot.get("video_model", "wan2.2"),
            "video_prompt": shot.get("video_prompt", ""),
            "video": None,
        }

    @staticmethod
    def _generate(generator: Any, job: dict[str, Any]) -> dict[str, Any]:
        refs = job["refs"]
        server = getattr(generator, "base_url", "")
        where = f" on {server}" if server else ""
        print(f"[SCENE] {job['name']}: generating{where}")
        print(f"[SCENE]   refs ({job['name']}): " + " | ".join(str(p) for p in refs))
        image = generator.generate(
            job["prompt"],
            job["negative"],
            job["dir"],
            "source.png",
            reference_images=refs,
        )
        print(f"[SCENE]   completed ({job['name']}): {image}")
        return SceneImageStage._record(job["scene"], job["shot"], image, refs)

    def run(
        self,
        story: dict[str, Any],
        movie_dir: Path,
        asset_refs: dict[str, Path],
    ) -> list[dict[str, Any]]:
        if not self.generators:
            raise RuntimeError("Scene image generation requested without an image generator")

        total_shots = sum(len(scene["shots"]) for scene in story["scenes"])
        label = self.cfg["label"]
        parallel = self.model == "qwen" and len(self.generators) > 1
        if len(self.generators) > 1 and not parallel:
            print(f"[SCENE] Parallel generation is qwen-only; running sequentially on the first server.")
        mode = f"parallel x{len(self.generators)}" if parallel else "sequential"
        print(f"[SCENE] Starting {total_shots} shot(s) with {label} (--scene-model {self.model}, {mode})")
        print(f"[SCENE] Model contract: image_prompt -> {label}; video_prompt -> WAN 2.2 only")

        records: list[dict[str, Any] | None] = [None] * total_shots
        pending: list[dict[str, Any]] = []

        shot_number = 0
        for scene in story["scenes"]:
            for shot in scene["shots"]:
                index = shot_number
                shot_number += 1
                shot_name = f"{scene['id']}/{shot['id']}"
                shot_dir = movie_dir / "scenes" / scene["id"] / shot["id"]
                destination = shot_dir / "source.png"

                print(f"[SCENE] Shot {shot_number}/{total_shots}: {shot_name}")
                if destination.exists():
                    print("[SCENE]   existing source.png found; skipping generation to preserve approved image.")
                    records[index] = self._record(scene, shot, destination, [])
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

                known = {c["image_model"] for c in SCENE_MODELS.values()}
                if shot.get("image_model", self.cfg["image_model"]) not in known:
                    raise ValueError(f"{shot_name} image_model must be one of {sorted(known)}")

                prompt = shot["image_prompt"]
                if self.cfg["picture_labels"]:
                    prompt = self._with_picture_labels(
                        prompt, asset_ids, story.get("reference_labels", {})
                    )
                job = {
                    "index": index, "name": shot_name, "scene": scene, "shot": shot,
                    "dir": shot_dir, "refs": refs, "prompt": prompt,
                    "negative": shot.get("negative_prompt", ""),
                }
                if parallel:
                    pending.append(job)  # validated now, generated below
                else:
                    records[index] = self._generate(self.generators[0], job)

        if pending:
            self._run_parallel(pending, records)

        done = [r for r in records if r is not None]
        print(f"[SCENE] Completed {len(done)}/{total_shots} scene image(s)")
        return done

    def _run_parallel(
        self, pending: list[dict[str, Any]], records: list[dict[str, Any] | None]
    ) -> None:
        """One worker per generator; a shot takes whichever server is free."""
        free: queue.Queue = queue.Queue()
        for g in self.generators:
            free.put(g)

        def work(job: dict[str, Any]) -> tuple[int, dict[str, Any]]:
            g = free.get()
            try:
                return job["index"], self._generate(g, job)
            finally:
                free.put(g)

        with ThreadPoolExecutor(max_workers=len(self.generators)) as pool:
            futures = [pool.submit(work, job) for job in pending]
            try:
                for future in as_completed(futures):
                    index, record = future.result()
                    records[index] = record
            except BaseException:
                # Stop queuing new shots; shots already running finish and keep
                # their source.png, so a rerun resumes where this left off.
                for f in futures:
                    f.cancel()
                raise