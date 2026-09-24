from __future__ import annotations

from pathlib import Path
from typing import Any
import json


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
        output_dir = self.root / category / asset_id
        existing = self.resolve(category, asset_id)

        # Versioned character references allow a corrected identity to replace
        # an already-generated bad reference without regenerating every asset.
        requested_version = asset.get("asset_prompt_version")
        version_file = output_dir / ".prompt_version"
        current_version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else None
        needs_regeneration = existing is None or (
            requested_version is not None and str(requested_version) != current_version
        )

        if not needs_regeneration:
            return existing

        if generator is None:
            raise RuntimeError(
                f"Missing asset '{category}/{asset_id}' and no image generator is configured"
            )

        prompt = asset["description"]
        negative = asset.get(
            "negative_prompt",
            "text, logo, watermark, distorted anatomy, duplicate subject",
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        generated = generator.generate(prompt, negative, output_dir, "reference.png")
        if requested_version is not None:
            version_file.write_text(str(requested_version), encoding="utf-8")
        return generated


class AssetStage:
    """Resolve named characters and supporting visual entities before scenes."""

    def __init__(self, library: AssetLibrary, generator: Any) -> None:
        self.library = library
        self.generator = generator

    def run(self, story: dict[str, Any]) -> dict[str, Path]:
        refs: dict[str, Path] = {}
        for asset in self._assets(story):
            refs[asset["id"]] = self.library.resolve_or_generate(
                asset,
                self.generator,
            )
        return refs

    @staticmethod
    def _assets(story: dict[str, Any]) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []

        for character in story.get("characters", []):
            item = dict(character)
            item.setdefault("category", "characters")
            assets.append(item)

        for location in story.get("locations", []):
            item = dict(location)
            item.setdefault("category", "locations")
            assets.append(item)

        for asset in story.get("supporting_assets", []):
            assets.append(dict(asset))

        return assets
