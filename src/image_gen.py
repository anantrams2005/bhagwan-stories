from __future__ import annotations
import copy, json, time, uuid
from pathlib import Path
from typing import Any
import requests

class ComfyUIImageGenerator:
    def __init__(self, base_url: str, workflow_path: Path, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.workflow_path = workflow_path
        self.timeout = timeout

    def generate(self, prompt: str, negative_prompt: str, output_dir: Path, output_name: str) -> Path:
        workflow = copy.deepcopy(json.loads(self.workflow_path.read_text(encoding="utf-8")))
        nodes = workflow.get("_pipeline_nodes", {})
        self._set_text(workflow, nodes.get("positive_prompt"), prompt)
        self._set_text(workflow, nodes.get("negative_prompt"), negative_prompt)
        client_id = str(uuid.uuid4())
        r = requests.post(f"{self.base_url}/prompt", json={"prompt": workflow, "client_id": client_id}, timeout=self.timeout)
        r.raise_for_status()
        image = self._wait_for_image(r.json()["prompt_id"])
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / output_name
        r = requests.get(f"{self.base_url}/view", params={"filename": image["filename"], "subfolder": image.get("subfolder", ""), "type": image.get("type", "output")}, timeout=self.timeout)
        r.raise_for_status()
        destination.write_bytes(r.content)
        return destination

    def _wait_for_image(self, prompt_id: str, poll_seconds: float = 1.0) -> dict[str, Any]:
        for _ in range(600):
            r = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=self.timeout)
            r.raise_for_status()
            history = r.json().get(prompt_id)
            if history:
                for output in history.get("outputs", {}).values():
                    if output.get("images"):
                        return output["images"][0]
            time.sleep(poll_seconds)
        raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")

    @staticmethod
    def _set_text(workflow: dict[str, Any], node_id: str | None, value: str) -> None:
        if not node_id or node_id not in workflow:
            return
        workflow[node_id].setdefault("inputs", {})["text"] = value
