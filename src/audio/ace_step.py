from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any


class AceStepMusicGenerator:
    """Generate instrumental timeline segments with ACE-Step 1.5's Python API.

    ACE-Step is intentionally kept outside this repository. Set ace_step_root to
    the local ACE-Step checkout so this project does not vendor the model or its
    large ML dependencies.
    """

    def __init__(
        self,
        ace_step_root: Path,
        checkpoint_dir: Path | None = None,
        dit_model: str = "acestep-v15-turbo",
        lm_model: str = "acestep-5Hz-lm-0.6B",
        device: str = "mps",
    ) -> None:
        self.root = Path(ace_step_root).expanduser().resolve()
        if not self.root.exists():
            raise FileNotFoundError(f"ACE-Step root does not exist: {self.root}")
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))

        try:
            from acestep.handler import AceStepHandler
            from acestep.llm_inference import LLMHandler
        except ImportError as exc:
            raise RuntimeError(
                "ACE-Step Python package is not importable. "
                "Point --ace-step-root at the ACE-Step 1.5 checkout."
            ) from exc

        self._handler_cls = AceStepHandler
        self._llm_cls = LLMHandler
        self.checkpoint_dir = Path(checkpoint_dir).expanduser().resolve() if checkpoint_dir else None
        self.dit_model = dit_model
        self.lm_model = lm_model
        self.device = device
        self._dit = None
        self._llm = None

    def _initialize(self) -> None:
        if self._dit is not None:
            return

        self._dit = self._handler_cls()
        self._dit.initialize_service(
            project_root=str(self.root),
            config_path=self.dit_model,
            device=self.device,
        )

        self._llm = self._llm_cls()
        if self.checkpoint_dir is None:
            raise RuntimeError(
                "--ace-step-checkpoints is required when using the ACE-Step music backend"
            )
        self._llm.initialize(
            checkpoint_dir=str(self.checkpoint_dir),
            lm_model_path=self.lm_model,
            backend="vllm" if self.device == "cuda" else "transformers",
            device=self.device,
        )

    def generate(
        self,
        caption: str,
        duration: float,
        output_dir: Path,
        filename: str,
        seed: int = -1,
    ) -> Path:
        self._initialize()
        from acestep.inference import GenerationConfig, GenerationParams, generate_music

        output_dir.mkdir(parents=True, exist_ok=True)
        params = GenerationParams(
            task_type="text2music",
            caption=caption,
            lyrics="[Instrumental]",
            instrumental=True,
            duration=max(10.0, min(600.0, float(duration))),
            inference_steps=8,
            shift=3.0,
            seed=seed,
        )
        config = GenerationConfig(
            batch_size=1,
            use_random_seed=(seed < 0),
            audio_format="wav",
        )
        result = generate_music(
            self._dit,
            self._llm,
            params,
            config,
            save_dir=str(output_dir),
        )
        if not result.success or not result.audios:
            raise RuntimeError(f"ACE-Step music generation failed: {result.error}")

        generated = Path(result.audios[0]["path"])
        destination = output_dir / filename
        if generated.resolve() != destination.resolve():
            destination.write_bytes(generated.read_bytes())
        return destination
