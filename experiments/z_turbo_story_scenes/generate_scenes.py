from __future__ import annotations

import copy
import json
import time
import uuid
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parent


class ComfyUI:
    def __init__(self, base_url: str, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(
        self,
        workflow_path: Path,
        prompt: str,
        negative: str,
        seed: int,
        width: int,
        height: int,
        steps: int,
        output_dir: Path,
        output_name: str,
        config: dict[str, Any],
    ) -> Path:
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        workflow = copy.deepcopy(workflow)

        metadata = workflow.pop("_pipeline_nodes", {})
        positive_node = config.get("positive_prompt_node") or metadata.get("positive_prompt")
        negative_node = config.get("negative_prompt_node") or metadata.get("negative_prompt")
        seed_node = config.get("seed_node") or metadata.get("seed")
        width_node = config.get("width_node") or metadata.get("width")
        height_node = config.get("height_node") or metadata.get("height")
        steps_node = metadata.get("steps")

        self._set(workflow, positive_node, "text", prompt)
        self._set(workflow, negative_node, "text", negative)
        self._set(workflow, seed_node, "seed", seed)
        self._set(workflow, width_node, "width", width)
        self._set(workflow, height_node, "height", height)
        self._set(workflow, steps_node, "steps", steps)

        client_id = str(uuid.uuid4())
        r = requests.post(
            f"{self.base_url}/prompt",
            json={"prompt": workflow, "client_id": client_id},
            timeout=self.timeout,
        )
        r.raise_for_status()
        payload = r.json()
        prompt_id = payload.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI returned no prompt_id: {payload}")

        print(f"[Z-TURBO] queued prompt={prompt_id} seed={seed}")
        image = self._wait(prompt_id)

        r = requests.get(
            f"{self.base_url}/view",
            params={
                "filename": image["filename"],
                "subfolder": image.get("subfolder", ""),
                "type": image.get("type", "output"),
            },
            timeout=self.timeout,
        )
        r.raise_for_status()

        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / output_name
        destination.write_bytes(r.content)
        return destination

    @staticmethod
    def _set(workflow: dict[str, Any], node_id: Any, key: str, value: Any) -> None:
        if node_id is None:
            return
        node_id = str(node_id)
        if node_id not in workflow:
            raise ValueError(f"Configured ComfyUI node {node_id!r} is not in the API workflow")
        workflow[node_id].setdefault("inputs", {})[key] = value

    def _wait(self, prompt_id: str) -> dict[str, Any]:
        for _ in range(600):
            r = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=self.timeout)
            r.raise_for_status()
            history = r.json().get(prompt_id)
            if history:
                status = history.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(json.dumps(status, ensure_ascii=False))
                for node_output in history.get("outputs", {}).values():
                    if node_output.get("images"):
                        return node_output["images"][0]
            time.sleep(1)
        raise TimeoutError(f"Timed out waiting for {prompt_id}")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_prompt(story: dict[str, Any], shot: dict[str, Any], scene: dict[str, Any]) -> str:
    cast = "\n".join(
        f"- {c['id']}: {c['description']}" for c in story.get("cast", [])
    )
    locations = "\n".join(
        f"- {x['id']}: {x['description']}" for x in story.get("locations", [])
    )

    return f"""Create one frame from the same cinematic 3D Indian animated movie.

VISUAL WORLD:
{story['visual_bible']}

RECURRING CAST — keep these identities, ages, body proportions, skin tones, hair, clothing and accessories consistent across every shot:
{cast}

RECURRING LOCATIONS:
{locations}

CURRENT STORY BEAT:
{scene.get('story_beat', '')}

CURRENT SHOT:
{shot['image_prompt']}

CONTINUITY RULES:
The same named characters must look like the same children/adults from previous shots.
Do not age characters up or down.
Do not change clothing colors.
Only Krishna has blue skin and only Krishna has one peacock feather.
Keep the grandmother and three children distinct from Krishna.
Do not add unnamed children.
The scene must be visually understandable without narration.
Use a cinematic movie composition with readable faces and meaningful foreground, middle-ground and background detail.
Do not make the characters tiny in a huge environment.
"""


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("story")
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    args = parser.parse_args()

    story_path = Path(args.story)
    config_path = Path(args.config)
    story = load(story_path)
    config = load(config_path)

    workflow_path = Path(config["workflow"])
    if not workflow_path.is_absolute():
        workflow_path = ROOT / workflow_path

    seed = int(story.get("seed", config["seed"]))
    out_root = ROOT / "output" / story["id"]
    comfy = ComfyUI(config["comfyui_url"])

    records = []
    total = sum(len(s["shots"]) for s in story["scenes"])
    index = 0

    print(f"[Z-TURBO] Story: {story['title']}")
    print(f"[Z-TURBO] Fixed story seed: {seed}")
    print(f"[Z-TURBO] Shots: {total}")

    for scene in story["scenes"]:
        for shot in scene["shots"]:
            index += 1
            prompt = build_prompt(story, shot, scene)
            destination = out_root / scene["id"] / f"{shot['id']}.png"

            print(f"\n[Z-TURBO] Shot {index}/{total}: {scene['id']}/{shot['id']}")
            image = comfy.generate(
                workflow_path,
                prompt,
                story.get("negative_prompt", ""),
                seed,
                int(config["width"]),
                int(config["height"]),
                int(config["steps"]),
                destination.parent,
                destination.name,
                config,
            )

            records.append({
                "scene_id": scene["id"],
                "shot_id": shot["id"],
                "seed": seed,
                "image": str(image),
                "prompt": prompt,
            })

    manifest = out_root / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n[Z-TURBO] Completed {len(records)}/{total}")
    print(f"[Z-TURBO] Manifest: {manifest}")


if __name__ == "__main__":
    main()
