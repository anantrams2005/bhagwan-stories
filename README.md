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
5. Run `combine_movie.py` locally. It reads the music timeline from the story JSON, generates each ACE-Step 1.5 segment, concatenates the clips in story order, and mixes the music into the final MP4.

## Music timeline

Music is intentionally story-specific. Each JSON has a top-level `music` object with a timeline, analogous to the dialogue timeline:

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

## Commands

Validate a story:

```bash
python generate_movie.py stories/generated/krishna_flute_qa_001.json --validate
```

Generate assets + scene images:

```bash
python generate_movie.py stories/generated/krishna_flute_qa_001.json \
  --image-backend comfyui \
  --asset-image-workflow workflows/z_turbo_assets.json \
  --scene-image-workflow workflows/flux2_klein_4b_scene.json
```

After Kaggle returns the I2V clips, combine and generate music:

```bash
python combine_movie.py stories/generated/krishna_flute_qa_001.json \
  --movie-dir output/krishna_flute_qa_001 \
  --music-backend ace_step \
  --ace-step-root /path/to/Ace-Step1.5 \
  --ace-step-checkpoints /path/to/checkpoints \
  --ace-step-device mps
```

`ACE_STEP_ROOT` can be used instead of `--ace-step-root`.

## Requirements

- Python 3.10+
- running ComfyUI for local image generation
- exported API-compatible ComfyUI workflows
- FFmpeg on PATH for assembly
- ACE-Step 1.5 checkout and model checkpoints for music generation
- Z-Turbo workflow for reusable asset generation
- FLUX.2 Klein 4B Image Edit workflow for scene generation

Install the lightweight repository dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

ACE-Step's large ML dependencies/checkpoints are kept outside this repository.

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
