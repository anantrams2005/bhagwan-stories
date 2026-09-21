from __future__ import annotations
import copy, json, time, uuid
from pathlib import Path
from typing import Any
import requests

class ComfyUIVideoGenerator:
    """Generic ComfyUI I2V adapter; workflow can target Wan 2.2 or another model."""

    def __init__(self, base_url: str, workflow_path: Path, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.workflow_path = workflow_path
        self.timeout = timeout

    def generate(self, image_path: Path, prompt: str, duration: float, output_dir: Path, output_name: str) -> Path:
        workflow = copy.deepcopy(json.loads(self.workflow_path.read_text(encoding="utf-8")))
        nodes = workflow.get("_pipeline_nodes", {})
        self._set_text(workflow, nodes.get("positive_prompt"), prompt)
        self._set_image(workflow, nodes.get("image"), image_path)
        if nodes.get("duration"):
            workflow[nodes["duration"]].setdefault("inputs", {})["value"] = duration
        client_id = str(uuid.uuid4())
        r = requests.post(f"{self.base_url}/prompt", json={"prompt": workflow, "client_id": client_id}, timeout=self.timeout)
        r.raise_for_status()
        media = self._wait_for_video(r.json()["prompt_id"])
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / output_name
        r = requests.get(f"{self.base_url}/view", params={"filename": media["filename"], "subfolder": media.get("subfolder", ""), "type": media.get("type", "output")}, timeout=self.timeout)
        r.raise_for_status()
        destination.write_bytes(r.content)
        return destination

    @staticmethod
    def _set_text(workflow: dict[str, Any], node_id: str | None, value: str) -> None:
        if node_id and node_id in workflow:
            workflow[node_id].setdefault("inputs", {})["text"] = value

    @staticmethod
    def _set_image(workflow: dict[str, Any], node_id: str | None, image_path: Path) -> None:
        if node_id and node_id in workflow:
            workflow[node_id].setdefault("inputs", {})["image"] = str(image_path)

    def _wait_for_video(self, prompt_id: str, poll_seconds: float = 2.0) -> dict[str, Any]:
        for _ in range(900):
            r = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=self.timeout)
            r.raise_for_status()
            history = r.json().get(prompt_id)
            if history:
                for output in history.get("outputs", {}).values():
                    for key in ("gifs", "videos"):
                        if output.get(key):
                            return output[key][0]
            time.sleep(poll_seconds)
        raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")
