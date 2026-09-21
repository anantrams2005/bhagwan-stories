from __future__ import annotations
from typing import Any


def validate_story(story: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("id", "title", "scenes"):
        if not story.get(key):
            errors.append(f"Missing required field: {key}")

    characters = story.get("characters", [])
    if characters and not isinstance(characters, list):
        errors.append("characters must be an array")
    for i, character in enumerate(characters if isinstance(characters, list) else []):
        if not character.get("id"):
            errors.append(f"characters[{i}] missing id")
        if not character.get("description"):
            errors.append(f"characters[{i}] missing description")

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
