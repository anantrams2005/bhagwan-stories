from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class MovieAssembler:
    """Assemble Kaggle-generated I2V clips, generated music and final MP4."""

    def __init__(self, ffmpeg: str = "ffmpeg") -> None:
        self.ffmpeg = ffmpeg

    def combine(self, story: dict[str, Any], movie_dir: Path, music_generator: Any | None = None) -> Path:
        movie_dir = Path(movie_dir)
        generated_videos = movie_dir / "generated_short_videos"
        music_dir = movie_dir / "audio" / "music"
        final_dir = movie_dir / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        music_dir.mkdir(parents=True, exist_ok=True)

        videos = self._ordered_videos(story, generated_videos)
        if not videos:
            raise RuntimeError(
                f"No I2V clips found in {generated_videos}. "
                "Copy the Kaggle-generated clips there before running combine."
            )

        video_path = final_dir / "video_only.mp4"
        self._concat_videos(videos, video_path)

        music = story.get("music", {})
        timeline = music.get("timeline", [])
        music_paths: list[tuple[Path, float, float]] = []
        if music_generator and timeline:
            for index, segment in enumerate(timeline, 1):
                start = float(segment["start"])
                end = float(segment["end"])
                duration = max(10.0, end - start)
                filename = segment.get("file", f"music_{index:02d}.wav")
                path = music_dir / filename
                if not path.exists():
                    music_generator.generate(
                        caption=segment["prompt"],
                        duration=duration,
                        output_dir=music_dir,
                        filename=filename,
                        seed=int(segment.get("seed", -1)),
                    )
                music_paths.append((path, start, end))

        final_path = final_dir / "final_short.mp4"
        if music_paths:
            self._mix_music(video_path, music_paths, final_path)
        else:
            shutil.copy2(video_path, final_path)

        manifest = {
            "story_id": story["id"],
            "title": story["title"],
            "videos": [str(p.relative_to(movie_dir)) for p in videos],
            "music": [
                {"file": str(p.relative_to(movie_dir)), "start": s, "end": e}
                for p, s, e in music_paths
            ],
            "final": str(final_path.relative_to(movie_dir)),
        }
        (final_dir / "assembly_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Final video: {final_path}")
        return final_path

    @staticmethod
    def _ordered_videos(story: dict[str, Any], root: Path) -> list[Path]:
        result: list[Path] = []
        for scene in story["scenes"]:
            for shot in scene["shots"]:
                shot_id = shot["id"]
                scene_id = scene["id"]
                candidates = [
                    root / scene_id / f"{shot_id}.mp4",
                    root / f"{shot_id}.mp4",
                    root / scene_id / shot_id / "shot.mp4",
                ]
                found = next((p for p in candidates if p.exists()), None)
                if found is None:
                    raise FileNotFoundError(
                        f"Missing I2V clip for {scene_id}/{shot_id}; looked under {root}"
                    )
                result.append(found)
        return result

    def _concat_videos(self, videos: list[Path], output: Path) -> None:
        inputs: list[str] = []
        filters: list[str] = []
        for i, video in enumerate(videos):
            inputs += ["-i", str(video)]
            filters.append(
                f"[{i}:v]setpts=PTS-STARTPTS,format=yuv420p[v{i}]"
            )
        joined = "".join(f"[v{i}]" for i in range(len(videos)))
        filters.append(f"{joined}concat=n={len(videos)}:v=1:a=0[v]")
        cmd = [
            self.ffmpeg, "-y", *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[v]", "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-movflags", "+faststart", str(output),
        ]
        self._run(cmd)

    def _mix_music(
        self,
        video: Path,
        music_paths: list[tuple[Path, float, float]],
        output: Path,
    ) -> None:
        inputs = ["-i", str(video)]
        filters: list[str] = []
        labels: list[str] = []
        for i, (path, start, end) in enumerate(music_paths, 1):
            inputs += ["-i", str(path)]
            duration = max(0.01, end - start)
            delay_ms = max(0, round(start * 1000))
            volume = 10 ** (-20 / 20)
            filters.append(
                f"[{i}:a]atrim=0:{duration},asetpts=PTS-STARTPTS,"
                f"adelay={delay_ms}|{delay_ms},volume={volume}[m{i}]"
            )
            labels.append(f"[m{i}]")
        filters.append(
            f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:dropout_transition=2:normalize=1[mix]"
        )
        filters.append("[0:v]setpts=PTS-STARTPTS[v]")
        cmd = [
            self.ffmpeg, "-y", *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[v]", "-map", "[mix]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", str(output),
        ]
        self._run(cmd)

    @staticmethod
    def _run(command: list[str]) -> None:
        print("[FFMPEG] " + " ".join(command))
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(
                "FFmpeg failed:\n" + (result.stderr[-6000:] or result.stdout[-6000:])
            )
