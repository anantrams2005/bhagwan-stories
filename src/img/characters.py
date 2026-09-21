from __future__ import annotations
from pathlib import Path
from typing import Any


class CharacterImageStage:
    """Create reusable character reference images before scene generation."""

    def __init__(self, generator: Any) -> None:
        self.generator = generator

    def run(self, story: dict[str, Any], output_dir: Path) -> dict[str, Path]:
        refs: dict[str, Path] = {}
        for character in story.get("characters", []):
            character_dir = output_dir / "characters" / character["id"]
            prompt = character["description"]
            negative = character.get("negative_prompt", "text, logo, watermark, distorted anatomy")
            refs[character["id"]] = self.generator.generate(prompt, negative, character_dir, "reference.png")
        return refs
