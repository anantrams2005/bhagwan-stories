from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import requests


class AceStepMusicGenerator:
    """Generate music through an already-running ACE-Step 1.5 HTTP service."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 3000.0,
        poll_interval: float = 1.0,
        poll_timeout: float = 1800.0,
        api_key: str | None = None,
        model: str | None = None,
        thinking: bool = True,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("ACE_STEP_URL") or "http://127.0.0.1:8001"
        ).rstrip("/")
        self.timeout = 3000
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self.api_key = api_key or os.environ.get("ACE_STEP_API_KEY")
        self.model = model
        self.thinking = thinking
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _url(self, path: str) -> str:
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def _json(self, response: requests.Response) -> dict[str, Any]:
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"ACE-Step returned non-JSON response from {response.url}: "
                f"{response.text[:1000]}"
            ) from exc
        if payload.get("code", 200) != 200:
            raise RuntimeError(f"ACE-Step API error: {payload.get('error') or payload}")
        return payload

    def _check_service(self) -> None:
        try:
            payload = self._json(
                self.session.get(self._url("/health"), timeout=self.timeout)
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Cannot reach ACE-Step API at {self.base_url}. "
                "Start the ACE-Step API server first."
            ) from exc
        status = payload.get("data", {}).get("status")
        if status not in (None, "ok"):
            raise RuntimeError(f"ACE-Step health check failed: {payload}")

    def _audio_url(self, audio_file: str) -> str:
        parsed = urlparse(audio_file)
        if parsed.scheme in ("http", "https"):
            return audio_file
        if audio_file.startswith("/v1/audio"):
            return self._url(audio_file)
        return self._url("/v1/audio") + "?path=" + quote(audio_file, safe="")

    def generate(
        self,
        caption: str,
        duration: float,
        output_dir: Path,
        filename: str,
        seed: int = -1,
    ) -> Path:
        self._check_service()
        output_dir.mkdir(parents=True, exist_ok=True)

        request_body: dict[str, Any] = {
            "prompt": caption,
            "lyrics": "[Instrumental]",
            "thinking": self.thinking,
            "task_type": "text2music",
            "audio_duration": max(10.0, min(600.0, float(duration))),
            "audio_format": "wav",
            "inference_steps": 8,
            "use_random_seed": seed < 0,
            "seed": seed,
            "batch_size": 1,
        }
        if self.model:
            request_body["model"] = self.model

        try:
            response = self.session.post(
                self._url("/release_task"), json=request_body, timeout=self.timeout
            )
            payload = self._json(response)
        except requests.RequestException as exc:
            raise RuntimeError(
                f"ACE-Step generation request failed at {self.base_url}: {exc}"
            ) from exc

        task_id = payload.get("data", {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"ACE-Step did not return a task_id: {payload}")

        deadline = time.monotonic() + self.poll_timeout
        result_items: list[dict[str, Any]] = []

        while time.monotonic() < deadline:
            try:
                response = self.session.post(
                    self._url("/query_result"),
                    json={"task_id_list": [task_id]},
                    timeout=self.timeout,
                )
                status_payload = self._json(response)
            except requests.RequestException as exc:
                raise RuntimeError(
                    f"ACE-Step result polling failed for task {task_id}: {exc}"
                ) from exc

            data = status_payload.get("data") or []
            if data:
                task = data[0]
                status = int(task.get("status", 0))
                if status == 1:
                    raw_result = task.get("result", "[]")
                    try:
                        result_items = (
                            json.loads(raw_result)
                            if isinstance(raw_result, str)
                            else raw_result
                        )
                    except json.JSONDecodeError as exc:
                        raise RuntimeError(
                            f"ACE-Step returned invalid result JSON for task {task_id}: "
                            f"{raw_result}"
                        ) from exc
                    break
                if status == 2:
                    raise RuntimeError(
                        f"ACE-Step music generation failed for task {task_id}: "
                        f"{task.get('error') or task}"
                    )

            time.sleep(self.poll_interval)
        else:
            raise TimeoutError(
                f"Timed out after {self.poll_timeout:.0f}s waiting for ACE-Step task {task_id}"
            )

        if not result_items:
            raise RuntimeError(
                f"ACE-Step task {task_id} succeeded without an audio result"
            )

        audio_file = result_items[0].get("file")
        if not audio_file:
            raise RuntimeError(
                f"ACE-Step task {task_id} returned no audio file: {result_items[0]}"
            )

        audio_url = self._audio_url(str(audio_file))

        try:
            audio_response = self.session.get(audio_url, timeout=self.timeout)
            audio_response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Failed to download ACE-Step audio from {audio_url}: {exc}"
            ) from exc

        destination = output_dir / filename
        destination.write_bytes(audio_response.content)
        return destination
