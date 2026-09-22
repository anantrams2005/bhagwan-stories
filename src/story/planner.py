from __future__ import annotations
from typing import Any


def build_plan(story: dict[str, Any]) -> dict[str, Any]:
    shots = [shot for scene in story["scenes"] for shot in scene["shots"]]
    return {
        "id": story["id"],
        "title": story["title"],
        "duration": sum(float(s["duration"]) for s in shots),
        "scene_count": len(story["scenes"]),
        "shot_count": len(shots),
        "character_count": len(story.get("characters", [])),
        "scenes": story["scenes"],
    }
