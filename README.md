# Bhagwan Stories — Cinematic Devotional Movie Pipeline

A Python-first pipeline for turning Indian mythology and devotional stories into short-form cinematic 3D mini-movies.

## Production flow

Each story is self-contained under `output/<story_id>/`:

```text
output/<story_id>/
├── story.json
├── scenes/
│   ├── scene_01/shot_01/source.png
│   └── ...
├── generated_short_videos/       # Kaggle I2V handoff / returned clips
│   ├── scene_01/shot_01.mp4
│   └── ...
├── audio/
│   └── music/                    # ACE-Step 1.5 generated WAVs
└── final/
    ├── video_only.mp4
    ├── final_short.mp4
    └── assembly_manifest.json
```

The intended workflow is:

1. Run `generate_movie.py` locally to generate reusable assets and scene source images.
2. Copy the whole story folder to the Kaggle WAN I2V notebook.
3. Generate the I2V clips in Kaggle.
4. Put the returned clips back under `generated_short_videos/<scene_id>/<shot_id>.mp4`.
5. Run `combine_movie.py` locally. It reads the music timeline from the story JSON, requests each ACE-Step 1.5 segment from the already-running local ACE-Step service, concatenates the clips in story order, and mixes the music into the final MP4.

## Music timeline

Music is story-specific. Each JSON has a top-level `music` object with a timeline:

```json
"music": {
  "provider": "ace_step",
  "model": "ACE-Step 1.5",
  "volume_db": -20,
  "timeline": [
    {
      "id": "music_01",
      "start": 0,
      "end": 6,
      "prompt": "Gentle playful Vrindavan devotional instrumental...",
      "volume_db": -20,
      "file": "music_01.wav"
    }
  ]
}
```

Segments are aligned to scene durations. This lets different parts of the same short have different musical moods without generating a new track for every shot. Music is instrumental and kept below dialogue level; dialogue/TTS is intentionally not implemented yet.

## ACE-Step service

The movie assembler does **not** import or initialize ACE-Step's Python model. This avoids loading a second copy of the model and avoids requiring ACE-Step's ML dependencies in the Bhagwan Stories Python environment.

The repository uses ACE-Step's HTTP API: submit a `/release_task`, poll `/query_result`, then download the returned `/v1/audio` file. ACE-Step documents the standalone REST API on port 8001 by default.

Start the ACE-Step API using the ACE-Step 1.5 checkout. Keep its existing Gradio UI on port 7860 if you use it; the movie pipeline talks to the API service.

Example:

```bash
cd /Users/anantagarwal/projects/music_gen/ACE-Step-1.5
./start_api_server_macos.sh
```

Then check:

```bash
curl http://127.0.0.1:8001/health
```

If your API is running on another port, use `--ace-step-url` or `ACE_STEP_URL`.

## Commands

Validate a story:

```bash
python generate_movie.py stories/generated/krishna_flute_qa_001.json --validate
```

After Kaggle returns the I2V clips, combine and generate music:

```bash
python combine_movie.py stories/generated/krishna_flute_qa_001.json \
  --movie-dir output/krishna_flute_qa_001 \
  --music-backend ace_step \
  --ace-step-url http://127.0.0.1:8001
```

The URL can also be configured with:

```bash
export ACE_STEP_URL=http://127.0.0.1:8001
```

No ACE-Step root, checkpoint directory, or `vector_quantize_pytorch` installation is required by this repository.

## Requirements

- Python 3.10+
- `requests` for the ACE-Step HTTP client
- running ComfyUI for local image generation
- exported API-compatible ComfyUI workflows
- FFmpeg on PATH for assembly
- separately running ACE-Step 1.5 service for music generation
- Z-Turbo workflow for reusable asset generation
- FLUX.2 Klein 4B Image Edit workflow for scene generation

Install the lightweight repository dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Design principles

1. **The story is shown, not explained.**
2. Every shot must advance the story.
3. Prefer believable restrained motion over complex choreography.
4. Character and environment continuity matter.
5. Build a strong source image before animation.
6. Keep model-specific details out of story JSON where possible.
7. Don't present invented devotional fiction as scripture.
8. Generate scene source images in 16:9; convert/crop for the final platform format later if needed.
9. Optimize for viewer retention, not a fixed shot count.
10. Keep image, video and audio backends replaceable.
