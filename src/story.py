from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def load_story(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def validate_story(story: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("id", "title", "scenes"):
        if not story.get(key):
            errors.append(f"Missing required field: {key}")
    if not isinstance(story.get("scenes"), list) or not story["scenes"]:
        errors.append("scenes must be a non-empty array")
        return errors
    for si, scene in enumerate(story["scenes"]):
        if not scene.get("id"):
            errors.append(f"scene[{si}] missing id")
        if not isinstance(scene.get("shots"), list) or not scene["shots"]:
            errors.append(f"scene[{si}] must contain at least one shot")
            continue
        for hi, shot in enumerate(scene["shots"]):
            p = f"scene[{si}].shot[{hi}]"
            for key in ("id", "duration", "image_prompt", "video_prompt"):
                if key not in shot:
                    errors.append(f"{p} missing {key}")
            if "duration" in shot and not isinstance(shot["duration"], (int, float)):
                errors.append(f"{p}.duration must be numeric")
    return errors

def build_plan(story: dict[str, Any]) -> dict[str, Any]:
    shots = [shot for scene in story["scenes"] for shot in scene["shots"]]
    return {
        "id": story["id"],
        "title": story["title"],
        "duration": sum(float(s["duration"]) for s in shots),
        "scene_count": len(story["scenes"]),
        "shot_count": len(shots),
        "scenes": story["scenes"],
    }
