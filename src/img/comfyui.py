from __future__ import annotations

import copy
import json
import re
import time
import uuid
import zlib
from pathlib import Path
from typing import Any

import requests


QWEN_ENCODE_CLASS = "TextEncodeQwenImageEditPlus"
QWEN_MAX_IMAGES = 3
SCENE_MODELS = ("qwen", "flux")


class ComfyUIImageGenerator:
    """ComfyUI image adapter for API-format workflows.

    Workflow-specific node mappings live in the workflow JSON under the
    _pipeline_nodes metadata key. That metadata is removed before submission.

    model selects scene-workflow behavior:
      "qwen"  Qwen-Image-Edit-2511: 1-3 refs (unused image inputs pruned),
              'Reference N' -> 'Picture N' in the prompt.
      "flux"  FLUX.2 Klein 4B: exactly as many refs as the workflow declares,
              prompt used unchanged.
      None    asset / non-scene workflows: no model-specific handling.
    """

    def __init__(
        self,
        base_url: str,
        workflow_path: Path,
        timeout: int = 120,
        model: str | None = None,
    ) -> None:
        if model is not None and model not in SCENE_MODELS:
            raise ValueError(f"model must be one of {SCENE_MODELS} or None; got {model!r}")
        self.base_url = base_url.rstrip("/")
        self.workflow_path = workflow_path
        self.timeout = timeout
        self.model = model

    def generate(
        self,
        prompt: str,
        negative_prompt: str,
        output_dir: Path,
        output_name: str,
        reference_images: list[Path] | None = None,
        seed: int | None = None,
    ) -> Path:
        print(f"[IMAGE] Loading workflow: {self.workflow_path}")
        workflow = copy.deepcopy(
            json.loads(self.workflow_path.read_text(encoding="utf-8"))
        )
        nodes = workflow.pop("_pipeline_nodes", {})

        if self.model == "qwen":
            prompt = self._to_picture_labels(prompt)
        self._set_text(workflow, nodes.get("positive_prompt"), prompt)
        # Negative text is accepted but unused: Lightning 4-step runs at cfg 1.
        self._set_text(workflow, nodes.get("negative_prompt"), negative_prompt)

        reference_slots = nodes.get("reference_images", [])
        if reference_slots:
            refs = [Path(p) for p in (reference_images or [])]
            missing = [str(p) for p in refs if not p.exists()]
            if missing:
                raise FileNotFoundError(f"Reference image(s) not found: {missing}")
            n = len(refs)
            min_refs = 1 if self.model == "qwen" else len(reference_slots)
            if not min_refs <= n <= len(reference_slots):
                expected = (
                    f"{min_refs} to {len(reference_slots)}"
                    if min_refs != len(reference_slots)
                    else str(len(reference_slots))
                )
                raise ValueError(
                    f"{self.workflow_path.name} requires {expected} reference images; "
                    f"received {n}"
                )
            uploaded = [self._upload_image(path) for path in refs]
            self._set_reference_images(workflow, reference_slots[:n], uploaded)
            if self.model == "qwen":
                self._prune_unused_images(workflow, nodes, n)
        elif reference_images:
            raise ValueError(
                f"{self.workflow_path.name} does not declare reference image slots"
            )

        # Per-shot deterministic seed (same shot -> same seed on re-run).
        if seed is None:
            seed = zlib.crc32(str(output_dir / output_name).encode("utf-8"))
        self._set_seed(workflow, nodes.get("seed"), seed)

        client_id = str(uuid.uuid4())
        response = requests.post(
            f"{self.base_url}/prompt",
            json={"prompt": workflow, "client_id": client_id},
            timeout=self.timeout,
        )
        if not response.ok:
            try:
                details = response.json()
            except ValueError:
                details = response.text
            raise RuntimeError(
                f"ComfyUI rejected {self.workflow_path.name} "
                f"(HTTP {response.status_code}): {json.dumps(details, ensure_ascii=False)}"
            )

        payload = response.json()
        prompt_id = payload.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI accepted workflow but returned no prompt_id: {payload}")

        print(f"[IMAGE] ComfyUI accepted workflow. prompt_id={prompt_id}")
        image = self._wait_for_image(prompt_id)
        output_dir.mkdir(parents=True, exist_ok=True)

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
        destination = output_dir / output_name
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

    def _wait_for_image(
        self,
        prompt_id: str,
        poll_seconds: float = 1.0,
        log_every_seconds: float = 10.0,
    ) -> dict[str, Any]:
        """Wait for the exact prompt, with queue/progress diagnostics.

        A scene can appear on disk before this call returns because ComfyUI
        writes the SaveImage output as soon as the graph finishes. The pipeline
        must still wait for the matching prompt_id before downloading it.
        """
        started = time.monotonic()
        next_log = started

        for _ in range(600):
            response = requests.get(
                f"{self.base_url}/history/{prompt_id}",
                timeout=self.timeout,
            )
            response.raise_for_status()
            history = response.json().get(prompt_id)

            if history:
                status = history.get("status", {})
                status_str = status.get("status_str", "unknown")
                completed = status.get("completed", False)
                messages = status.get("messages", [])

                if status_str == "error" or status.get("status_str") == "error":
                    raise RuntimeError(
                        f"ComfyUI prompt {prompt_id} failed: "
                        f"{json.dumps(messages, ensure_ascii=False)}"
                    )

                for output in history.get("outputs", {}).values():
                    if output.get("images"):
                        elapsed = time.monotonic() - started
                        print(
                            f"[IMAGE] Completed prompt_id={prompt_id} "
                            f"after {elapsed:.1f}s"
                        )
                        return output["images"][0]

                if completed:
                    raise RuntimeError(
                        f"ComfyUI marked prompt {prompt_id} complete but returned no images: "
                        f"{json.dumps(history, ensure_ascii=False)}"
                    )

            now = time.monotonic()
            if now >= next_log:
                queue = self._queue_snapshot()
                queue_text = self._format_queue(queue, prompt_id)
                elapsed = now - started
                print(
                    f"[IMAGE] Waiting for prompt_id={prompt_id} "
                    f"({elapsed:.0f}s){queue_text}"
                )
                next_log = now + log_every_seconds

            time.sleep(poll_seconds)

        raise TimeoutError(
            f"Timed out waiting for ComfyUI prompt {prompt_id} after "
            f"{600 * poll_seconds:.0f}s"
        )

    def _queue_snapshot(self) -> dict[str, Any]:
        try:
            response = requests.get(f"{self.base_url}/queue", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return {}

    @staticmethod
    def _format_queue(queue: dict[str, Any], prompt_id: str) -> str:
        running = queue.get("queue_running", [])
        pending = queue.get("queue_pending", [])
        running_ids = {str(item[1]) for item in running if len(item) > 1}
        pending_ids = {str(item[1]) for item in pending if len(item) > 1}

        if prompt_id in running_ids:
            return " [queue=running]"
        if prompt_id in pending_ids:
            position = next(
                (i + 1 for i, item in enumerate(pending) if len(item) > 1 and str(item[1]) == prompt_id),
                "?",
            )
            return f" [queue=pending position={position}]"
        if running:
            return f" [queue=other-job-running pending={len(pending)}]"
        return f" [queue=idle pending={len(pending)}]"

    @staticmethod
    def _to_picture_labels(prompt: str) -> str:
        """Qwen-Image-Edit-Plus addresses inputs as 'Picture N'."""
        return re.sub(r"\bReference (\d)\b", r"Picture \1", prompt)

    @staticmethod
    def _set_text(workflow: dict[str, Any], node_id: str | None, value: str) -> None:
        if not node_id or node_id not in workflow:
            return
        node = workflow[node_id]
        inputs = node.setdefault("inputs", {})
        # TextEncodeQwenImageEditPlus uses 'prompt'; plain CLIPTextEncode uses 'text'.
        key = "prompt" if node.get("class_type") == QWEN_ENCODE_CLASS or "prompt" in inputs else "text"
        inputs[key] = value

    @staticmethod
    def _prune_unused_images(
        workflow: dict[str, Any], nodes: dict[str, Any], n_refs: int
    ) -> None:
        """Drop image{n+1..3} inputs on every Qwen encode node.

        Their LoadImage/scale nodes then are unreachable from SaveImage, so
        ComfyUI never executes them.
        """
        encode_ids = nodes.get("encode_nodes") or [
            nid for nid, node in workflow.items()
            if isinstance(node, dict) and node.get("class_type") == QWEN_ENCODE_CLASS
        ]
        if not encode_ids:
            raise ValueError(f"No {QWEN_ENCODE_CLASS} node found in workflow")
        for nid in encode_ids:
            inputs = workflow[nid].setdefault("inputs", {})
            for i in range(n_refs + 1, QWEN_MAX_IMAGES + 1):
                inputs.pop(f"image{i}", None)

    @staticmethod
    def _set_seed(workflow: dict[str, Any], node_id: str | None, seed: int) -> None:
        if not node_id or node_id not in workflow:
            return
        inputs = workflow[node_id].setdefault("inputs", {})
        inputs["noise_seed" if "noise_seed" in inputs else "seed"] = seed
