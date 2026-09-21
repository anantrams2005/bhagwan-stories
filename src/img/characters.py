from __future__ import annotations

from pathlib import Path
from typing import Any

from .assets import AssetLibrary, AssetStage


class CharacterImageStage(AssetStage):
    """Backward-compatible character-only asset stage.

    Existing references are reused; missing references are generated once.
    """

    def __init__(self, generator: Any, asset_root: Path = Path("assets")) -> None:
        super().__init__(AssetLibrary(asset_root), generator)
