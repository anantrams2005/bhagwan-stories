from __future__ import annotations

import copy
import json
import time
import uuid
from pathlib import Path
from typing import Any

import requests


class ComfyUIImageGenerator:
    """ComfyUI image adapter for API-format workflows.

    Workflow-specific node mappings live in the workflow JSON under the
    _pipeline_nodes metadata key. That metadata is removed before the workflow
    is submitted to ComfyUI.

    The bundled Klein scene workflow has three active reference-image slots:
    76 -> image, 81 -> image_1, 146 -> image_2 on the Image Edit graph.
    """

    def __init__(self, base_url: str, workflow_path: Path, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.workflow_path = workflow_path
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        negative_prompt: str,
        output_dir: Path,
        output_name: str,
        reference_images: list[Path] | None = None,
    ) -> Path:
        workflow = copy.deepcopy(
            json.loads(self.workflow_path.read_text(encoding="utf-8"))
        )
        nodes = workflow.pop("_pipeline_nodes", {})

        self._set_text(workflow, nodes.get("positive_prompt"), prompt)
        self._set_text(workflow, nodes.get("negative_prompt"), negative_prompt)

        reference_slots = nodes.get("reference_images", [])
        if reference_slots:
            refs = [Path(p) for p in (reference_images or []) if Path(p).exists()]
            expected = len(reference_slots)
            if len(refs) != expected:
                raise ValueError(
                    f"{self.workflow_path.name} requires {expected} reference images; "
                    f"received {len(refs)}"
                )
            uploaded = [self._upload_image(path) for path in refs]
            self._set_reference_images(workflow, reference_slots, uploaded)
        elif reference_images:
            raise ValueError(
                f"{self.workflow_path.name} does not declare reference image slots"
            )

        client_id = str(uuid.uuid4())
        response = requests.post(
            f"{self.base_url}/prompt",
            json={"prompt": workflow, "client_id": client_id},
            timeout=self.timeout,
        )
        response.raise_for_status()

        image = self._wait_for_image(response.json()["prompt_id"])
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / output_name

        response = requests.get(
            f"{self.base_url}/view",
            params={
                "filename": image["filename"],
                "subfolder": image.get("subfolder", ""),
                "type": image.get("type", "output"),
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        destination.write_bytes(response.content)
        return destination

    def _upload_image(self, path: Path) -> str:
        with path.open("rb") as handle:
            response = requests.post(
                f"{self.base_url}/upload/image",
                files={"image": (path.name, handle, "image/png")},
                data={"overwrite": "true"},
                timeout=self.timeout,
            )
        response.raise_for_status()
        return response.json()["name"]

    @staticmethod
    def _set_reference_images(
        workflow: dict[str, Any],
        node_ids: list[str],
        uploaded_names: list[str],
    ) -> None:
        for node_id, image_name in zip(node_ids, uploaded_names):
            if node_id not in workflow:
                raise ValueError(
                    f"Reference image node {node_id!r} is not present in workflow"
                )
            workflow[node_id].setdefault("inputs", {})["image"] = image_name

    def _wait_for_image(self, prompt_id: str, poll_seconds: float = 1.0) -> dict[str, Any]:
        for _ in range(600):
            response = requests.get(
                f"{self.base_url}/history/{prompt_id}",
                timeout=self.timeout,
            )
            response.raise_for_status()
            history = response.json().get(prompt_id)
            if history:
                for output in history.get("outputs", {}).values():
                    if output.get("images"):
                        return output["images"][0]
            time.sleep(poll_seconds)
        raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")

    @staticmethod
    def _set_text(workflow: dict[str, Any], node_id: str | None, value: str) -> None:
        if node_id and node_id in workflow:
            workflow[node_id].setdefault("inputs", {})["text"] = value
