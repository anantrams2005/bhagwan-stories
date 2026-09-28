from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests


class ComfyUIVideoGenerator:
    """Run a ComfyUI WAN I2V API workflow for one shot."""

    def __init__(self, base_url: str, workflow_path: Path) -> None:
        self.base_url = base_url.rstrip("/")
        self.workflow_path = workflow_path

    def generate(self, image: Path, prompt: str, duration: float, fps: float, output_dir: Path, filename: str) -> Path:
        workflow = json.loads(self.workflow_path.read_text(encoding="utf-8"))
        nodes = workflow.pop("_pipeline_nodes", {})
        required = ("positive_prompt", "image", "frames", "fps")
        missing = [key for key in required if not nodes.get(key)]
        if missing:
            raise ValueError(f"{self.workflow_path} missing _pipeline_nodes: {', '.join(missing)}")

        frames = max(1, round(duration * fps) + 1)
        uploaded_name = self._upload_image(image)
        self._set_text(workflow, nodes["positive_prompt"], prompt)
        self._set_value(workflow, nodes["image"], uploaded_name)
        self._set_value(workflow, nodes["frames"], frames)
        self._set_value(workflow, nodes["fps"], fps)

        response = requests.post(f"{self.base_url}/prompt", json={"prompt": workflow}, timeout=60)
        response.raise_for_status()
        prompt_id = response.json()["prompt_id"]

        while True:
            response = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=30)
            response.raise_for_status()
            history = response.json()
            if prompt_id in history:
                result = history[prompt_id]
                if result.get("status", {}).get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI video workflow failed: {result}")
                if "outputs" in result:
                    outputs = result["outputs"]
                    break
            time.sleep(1)

        for node_output in outputs.values():
            for key in ("gifs", "videos"):
                for item in node_output.get(key, []):
                    response = requests.get(
                        f"{self.base_url}/view",
                        params={"filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": item.get("type", "output")},
                        timeout=120,
                    )
                    response.raise_for_status()
                    output_dir.mkdir(parents=True, exist_ok=True)
                    path = output_dir / filename
                    path.write_bytes(response.content)
                    return path

        raise RuntimeError("ComfyUI video workflow completed without a video output")

    def _upload_image(self, image: Path) -> str:
        if not image.exists():
            raise FileNotFoundError(image)
        with image.open("rb") as handle:
            response = requests.post(
                f"{self.base_url}/upload/image",
                files={"image": (image.name, handle, "image/png")},
                data={"overwrite": "true"},
                timeout=120,
            )
        response.raise_for_status()
        return response.json().get("name") or image.name

    @staticmethod
    def _set_text(workflow: dict[str, Any], node_id: str, value: str) -> None:
        if node_id not in workflow:
            raise ValueError(f"Workflow node {node_id!r} not found")
        workflow[node_id]["inputs"]["text"] = value

    @staticmethod
    def _set_value(workflow: dict[str, Any], node_id: str, value: Any) -> None:
        if node_id not in workflow:
            raise ValueError(f"Workflow node {node_id!r} not found")
        inputs = workflow[node_id]["inputs"]
        for key in ("value", "duration", "fps", "frame_rate", "frames", "length", "image"):
            if key in inputs:
                inputs[key] = value
                return
        raise ValueError(f"Workflow node {node_id!r} has no supported runtime input")
