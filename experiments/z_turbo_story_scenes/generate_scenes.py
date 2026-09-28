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
        workflow = copy.deepcopy(json.loads(workflow_path.read_text(encoding="utf-8")))
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


def indexed_story(story: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for key in ("characters", "locations", "supporting_assets"):
        for item in story.get(key, []):
            index[item["id"]] = item
    return index


def describe_refs(story: dict[str, Any], shot: dict[str, Any]) -> str:
    index = indexed_story(story)
    lines = []
    for ref_id in shot.get("assets", shot.get("characters", [])):
        item = index.get(ref_id)
        if item:
            lines.append(f"- {ref_id}: {item.get('description', '')}")
    return "\n".join(lines)


def build_prompt(story: dict[str, Any], shot: dict[str, Any], scene: dict[str, Any]) -> str:
    index = indexed_story(story)
    refs = shot.get("assets", shot.get("characters", []))
    ref_text = describe_refs(story, shot)

    # Pull the story's actual action instead of reusing its old Klein reference prompt.
    action = shot.get("action", "").strip()
    camera = shot.get("camera", "").strip()
    purpose = scene.get("purpose", "").strip()

    krishna = index.get("krishna", {}).get("description", "")
    grandparents = [
        item for item in story.get("characters", [])
        if item["id"] in {"grandfather", "grandmother"}
    ]
    children = [
        item for item in story.get("characters", [])
        if item["id"].startswith("grandchild")
    ]

    continuity = f"""
KRISHNA IDENTITY — HARD:
{krishna}

Only Krishna has blue/Shyam-varna skin.
Every other human character MUST have natural Indian human skin tones.
Never give blue skin to a grandparent, Radha, Yashoda, cowherd, boatman, village child, or any other person.
Krishna is a small 6–8-year-old child, slim and pre-adolescent, never an adult, teenager, muscular or chubby.
Krishna alone has exactly ONE peacock feather.

STORYTELLING CAST:
Grandparent/narrator and listening children are separate from Krishna. If a shot is in the storytelling frame, Krishna is NOT one of the listeners unless the shot explicitly says the imagined story has entered the scene.
Never turn the grandparent into a character inside Krishna's historical scene.
Never make Krishna sit with the grandchildren unless the current action explicitly requires it.

VISUAL CONTINUITY:
Use the same cinematic stylized 3D Indian animated-movie world in every shot.
Preserve character age, body proportions, skin tone, hair, clothing and defining accessories.
Do not invent characters that are not required by the current action.
Keep important story objects physically consistent.
Make the current action visually obvious rather than merely decorative.
Characters should occupy enough of the frame for faces, hands and actions to be readable; do not make them tiny in a huge environment.
"""

    negative = story.get("generation", {}).get("negative_prompt", "")
    if not negative:
        negative = story.get("negative_prompt", "")
    negative += (
        ", photorealistic, photograph, live action, real person, "
        "blue skin on anyone except Krishna, blue grandfather, blue grandmother, "
        "blue Radha, blue cowherd, blue village child, extra Krishna, duplicate Krishna, "
        "extra peacock feather, peacock feather on anyone except Krishna, adult Krishna, "
        "teenage Krishna, muscular Krishna, chubby Krishna, extra children, invented characters, "
        "story mismatch, unrelated scene, text, logo, watermark"
    )

    return f"""Create ONE cinematic 3D Indian animated-movie frame in 16:9.

THIS IS A STORY FRAME, NOT AN ASSET SHEET.

STORY TITLE:
{story.get('title', story.get('id', ''))}

SCENE PURPOSE:
{purpose}

CURRENT ACTION — THIS MUST BE THE VISUAL STORY:
{action}

CAMERA / COMPOSITION:
{camera}

SUBJECTS AND LOCATIONS REQUIRED FOR THIS SHOT:
{ref_text}

GLOBAL VISUAL WORLD:
Cinematic stylized 3D Indian devotional animation, polished feature-film CGI, detailed Indian environments and props, expressive child-friendly faces, natural cinematic lighting, rich depth and atmosphere, believable materials, strong readable composition.

{continuity}

SHOT-SPECIFIC RULE:
Do not copy the old image_prompt instructions from the source JSON.
Reconstruct the frame from the CURRENT ACTION and the listed subjects/locations.
Do not change the story beat, invent a different event, or merge unrelated scenes.
If the current action says the grandparent is narrating beneath a banyan tree, show the grandparent and listening children beneath the banyan tree.
If the current action describes Krishna's leela, show Krishna and the explicitly named characters in that leela scene instead.
The historical Krishna scene and the modern storytelling frame are visually separate worlds.

CURRENT REFERENCE IDS:
{", ".join(refs)}
"""


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("story")
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    story_path = Path(args.story)
    config = load(Path(args.config))
    story = load(story_path)

    workflow_path = Path(config["workflow"])
    if not workflow_path.is_absolute():
        workflow_path = ROOT / workflow_path

    seed = int(args.seed if args.seed is not None else story.get("seed", config["seed"]))
    out_root = ROOT / "output" / story["id"]
    comfy = ComfyUI(config["comfyui_url"])

    records = []
    total = sum(len(s["shots"]) for s in story["scenes"])
    index = 0

    print(f"[Z-TURBO] Story: {story.get('title', story['id'])}")
    print(f"[Z-TURBO] Fixed story seed: {seed}")
    print(f"[Z-TURBO] Shots: {total}")

    for scene in story["scenes"]:
        for shot in scene["shots"]:
            index += 1
            prompt = build_prompt(story, shot, scene)
            destination = out_root / scene["id"] / f"{shot['id']}.png"

            print(f"\n[Z-TURBO] Shot {index}/{total}: {scene['id']}/{shot['id']}")
            print(f"[Z-TURBO] Action: {shot.get('action', '')}")

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
                "action": shot.get("action", ""),
                "prompt": prompt,
            })

    manifest = out_root / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[Z-TURBO] Completed {len(records)}/{total}")
    print(f"[Z-TURBO] Manifest: {manifest}")


if __name__ == "__main__":
    main()
