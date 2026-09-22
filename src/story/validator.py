from __future__ import annotations

from typing import Any

ASSET_CATEGORIES = {"characters", "people", "animals", "locations", "props"}


def validate_story(story: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for key in ("id", "title", "scenes"):
        if not story.get(key):
            errors.append(f"Missing required field: {key}")

    for field in ("characters", "locations", "supporting_assets"):
        value = story.get(field, [])
        if not isinstance(value, list):
            errors.append(f"{field} must be an array")
            continue
        for i, asset in enumerate(value):
            p = f"{field}[{i}]"
            if not isinstance(asset, dict):
                errors.append(f"{p} must be an object")
                continue
            if not asset.get("id"):
                errors.append(f"{p} missing id")
            if not asset.get("description"):
                errors.append(f"{p} missing description")
            if field == "supporting_assets" and asset.get("category") not in (
                ASSET_CATEGORIES - {"characters", "locations"}
            ):
                errors.append(f"{p}.category must be one of people, animals, props")

    if not isinstance(story.get("scenes"), list) or not story["scenes"]:
        errors.append("scenes must be a non-empty array")
        return errors

    known_assets = {
        a["id"]
        for field in ("characters", "locations", "supporting_assets")
        for a in story.get(field, [])
        if isinstance(a, dict) and a.get("id")
    }

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

            for asset_id in shot.get("assets", shot.get("characters", [])):
                if asset_id not in known_assets:
                    errors.append(f"{p} references unknown asset: {asset_id}")

    return errors
