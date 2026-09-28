from __future__ import annotations

from pathlib import Path
from typing import Any


class AssetLibrary:
    """Persistent reusable visual assets shared across movies."""

    CATEGORIES = ("characters", "people", "animals", "locations", "props")

    # Bump this whenever the global reusable-asset visual language changes.
    # Unlike asset_prompt_version, this invalidates every cached reference,
    # including old assets that have no per-asset version field.
    ASSET_STYLE_VERSION = "2"

    def __init__(self, root: Path) -> None:
        self.root = root

    def resolve(self, category: str, asset_id: str) -> Path | None:
        if category not in self.CATEGORIES:
            raise ValueError(f"Unsupported asset category: {category}")
        path = self.root / category / asset_id / "reference.png"
        return path if path.exists() else None

    @staticmethod
    def _style_prefix(category: str) -> str:
        if category in {"characters", "people", "animals"}:
            subject_kind = "character/creature"
        elif category == "locations":
            subject_kind = "environment"
        else:
            subject_kind = "prop/object"

        return (
            "Cinematic stylized 3D Indian devotional animation "
            f"{subject_kind} asset reference. "
            "Feature-film-quality 3D animated design, family-friendly Indian "
            "animation, expressive but natural stylized forms, detailed "
            "traditional clothing/materials where applicable, cinematic studio "
            "lighting, gentle depth of field, polished 3D render. "
            "This is a designed 3D animated movie asset, NOT a photograph, "
            "NOT a real person, NOT live action. Show the full subject clearly, "
            "centered, on a simple uncluttered neutral studio background. "
            "All reusable assets must belong to the same cinematic 3D visual world."
        )

    @staticmethod
    def _negative_prompt(asset: dict[str, Any]) -> str:
        required = (
            "photorealistic, photograph, photo, real person, live action, "
            "DSLR photo, realistic human portrait, photographic skin texture, "
            "text, logo, watermark, distorted anatomy, duplicate subject"
        )
        custom = asset.get("negative_prompt", "").strip()
        return f"{custom}, {required}" if custom else required

    def resolve_or_generate(
        self,
        asset: dict[str, Any],
        generator: Any,
    ) -> Path:
        category = asset.get("category", "characters")
        asset_id = asset["id"]
        output_dir = self.root / category / asset_id
        existing = self.resolve(category, asset_id)

        requested_version = asset.get("asset_prompt_version")
        version_file = output_dir / ".prompt_version"
        style_version_file = output_dir / ".asset_style_version"

        current_version = (
            version_file.read_text(encoding="utf-8").strip()
            if version_file.exists()
            else None
        )
        current_style_version = (
            style_version_file.read_text(encoding="utf-8").strip()
            if style_version_file.exists()
            else None
        )

        needs_regeneration = (
            existing is None
            or (
                requested_version is not None
                and str(requested_version) != current_version
            )
            or current_style_version != self.ASSET_STYLE_VERSION
        )

        if not needs_regeneration:
            return existing

        if generator is None:
            raise RuntimeError(
                f"Missing asset '{category}/{asset_id}' and no image generator is configured"
            )

        prompt = (
            self._style_prefix(category)
            + " Preserve the following identity/object details exactly: "
            + asset["description"]
        )
        negative = self._negative_prompt(asset)

        print(
            f"[ASSET] Generating {category}/{asset_id} "
            f"(style v{self.ASSET_STYLE_VERSION}, prompt v{requested_version or 'default'})"
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        generated = generator.generate(prompt, negative, output_dir, "reference.png")

        # Only mark the versions after the image was successfully generated.
        if requested_version is not None:
            version_file.write_text(str(requested_version), encoding="utf-8")
        style_version_file.write_text(self.ASSET_STYLE_VERSION, encoding="utf-8")
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
