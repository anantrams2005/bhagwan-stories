from __future__ import annotations

from typing import Any

from .assets import AssetStage


class SupportingAssetStage(AssetStage):
    """Semantic alias for village people, children, animals, locations and props.

    Reuse is keyed by category + asset id. Different instances should use
    different ids when the story needs visual variety.
    """

    def run(self, story: dict[str, Any]) -> dict[str, Any]:
        return super().run(story)
