from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests


class ComfyUIVideoGenerator:
    """ComfyUI I2V adapter. Timing values come from story JSON, not hardcoded here."""

    def __init__(self, base_url: str, workflow_path: Path) -> None:
        self.base_url = base_url.rstrip("/")
        self.workflow_path = workflow_path

    def generate(
        self,
        image: Path,
        prompt: str,
        duration: float,
        fps: float,
        output_dir: Path,
        filename: str,
    ) -> Path:
        workflow = json.loads(self.workflow_path.read_text(encoding="utf-8"))
        nodes = workflow.pop("_pipeline_nodes", {})
        frames = max(1, round(duration * fps) + 1)

        uploaded_name = self._upload_image(image)
        self._set_text(workflow, nodes.get("positive_prompt"), prompt)
        self._set_value(workflow, nodes.get("duration"), duration)
        self._set_value(workflow, nodes.get("fps"), fps)
        self._set_value(workflow, nodes.get("frames"), frames)
        self._set_value(workflow, nodes.get("image"), uploaded_name)

        response = requests.post(
            f"{self.base_url}/prompt", json={"prompt": workflow}, timeout=60
        )
        response.raise_for_status()
        prompt_id = response.json()["prompt_id"]

        while True:
            history = requests.get(
                f"{self.base_url}/history/{prompt_id}", timeout=30
            ).json()
            if prompt_id in history:
                result = history[prompt_id]
                if result.get("status", {}).get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI video workflow failed: {result}")
                outputs = result.get("outputs", {})
                break
            time.sleep(1)

        for node_output in outputs.values():
            for key in ("gifs", "videos"):
                for item in node_output.get(key, []):
                    name = item["filename"]
                    subfolder = item.get("subfolder", "")
                    kind = item.get("type", "output")
                    data = requests.get(
                        f"{self.base_url}/view",
                        params={"filename": name, "subfolder": subfolder, "type": kind},
                        timeout=120,
                    )
                    data.raise_for_status()
                    output_dir.mkdir(parents=True, exist_ok=True)
                    path = output_dir / filename
                    path.write_bytes(data.content)
                    return path

        raise RuntimeError("ComfyUI video workflow completed without a video output")

    def _upload_image(self, image: Path) -> str:
        with image.open("rb") as handle:
            response = requests.post(
                f"{self.base_url}/upload/image",
                files={"image": (image.name, handle, "image/png")},
                data={"overwrite": "true"},
                timeout=120,
            )
        response.raise_for_status()
        payload = response.json()
        return payload.get("name") or image.name

    @staticmethod
    def _set_text(workflow: dict[str, Any], node_id: str | None, value: str) -> None:
        if node_id and node_id in workflow:
            workflow[node_id]["inputs"]["text"] = value

    @staticmethod
    def _set_value(workflow: dict[str, Any], node_id: str | None, value: Any) -> None:
        if node_id and node_id in workflow:
            inputs = workflow[node_id]["inputs"]
            for key in ("value", "duration", "fps", "frame_rate", "frames", "length", "image"):
                if key in inputs:
                    inputs[key] = value
                    return
