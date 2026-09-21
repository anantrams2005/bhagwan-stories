from __future__ import annotations

from pathlib import Path
from typing import Any


class AssetLibrary:
    """Persistent reusable visual assets shared across movies."""

    CATEGORIES = ("characters", "people", "animals", "locations", "props")

    def __init__(self, root: Path) -> None:
        self.root = root

    def resolve(self, category: str, asset_id: str) -> Path | None:
        if category not in self.CATEGORIES:
            raise ValueError(f"Unsupported asset category: {category}")
        path = self.root / category / asset_id / "reference.png"
        return path if path.exists() else None

    def resolve_or_generate(
        self,
        asset: dict[str, Any],
        generator: Any,
    ) -> Path:
        category = asset.get("category", "characters")
        asset_id = asset["id"]
        existing = self.resolve(category, asset_id)
        if existing:
            return existing

        if generator is None:
            raise RuntimeError(
                f"Missing asset '{category}/{asset_id}' and no image generator is configured"
            )

        output_dir = self.root / category / asset_id
        prompt = asset["description"]
        negative = asset.get(
            "negative_prompt",
            "text, logo, watermark, distorted anatomy, duplicate subject",
        )
        return generator.generate(prompt, negative, output_dir, "reference.png")


class AssetStage:
    """Resolve named characters and supporting visual entities before scenes."""

    def __init__(self, library: AssetLibrary, generator: Any) -> None:
        self.library = library
        self.generator = generator

    def run(self, story: dict[str, Any]) -> dict[str, Path]:
        refs: dict[str, Path] = {}
        for asset in self._assets(story):
            refs[asset["id"]] = self.library.resolve_or_generate(asset, self.generator)
        return refs

    @staticmethod
    def _assets(story: dict[str, Any]) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []

        for character in story.get("characters", []):
            item = dict(character)
            item.setdefault("category", "characters")
            assets.append(item)

        for asset in story.get("supporting_assets", []):
            assets.append(dict(asset))

        return assets
