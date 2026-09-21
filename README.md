# Bhagwan Stories — Cinematic Devotional Movie Pipeline

A Python-first pipeline for turning Indian mythology and devotional stories into short-form cinematic 3D mini-movies.

The goal is **story-first visual filmmaking**, not documentary narration or slideshow reels.

## Pipeline

```
Story JSON → scene/shot plan → image generation → image-to-video → audio → edit
```

This first implementation keeps model-specific workflows outside the story format.

## Current scope

- Python CLI
- JSON story input and validation
- deterministic movie/scene/shot output directories
- ComfyUI image-generation adapter
- generic ComfyUI image-to-video adapter intended for Wan 2.2
- master prompt for asking ChatGPT to produce cinematic story breakdowns
- sample Radha-Krishna story

Audio and final editing are extension points for the next stages.

## Requirements

- Python 3.10+
- running ComfyUI for image generation
- an exported ComfyUI image workflow

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Validate:

```bash
python generate_movie.py stories/examples/krishna_flute.json --validate
```

Create a production plan without generating media:

```bash
python generate_movie.py stories/examples/krishna_flute.json --plan
```

Generate images:

```bash
python generate_movie.py stories/examples/krishna_flute.json \
  --image-backend comfyui \
  --comfyui-url http://127.0.0.1:8188 \
  --image-workflow workflows/image_workflow.json
```

Generate I2V after images:

```bash
python generate_movie.py stories/examples/krishna_flute.json \
  --image-backend comfyui \
  --image-workflow workflows/image_workflow.json \
  --video-backend comfyui_wan \
  --video-workflow workflows/wan_i2v_workflow.json
```

The workflows are intentionally external because the exact ComfyUI graphs will depend on the installed model/version.

## Design principles

1. **The story is shown, not explained.**
2. Every shot must advance the story.
3. Prefer believable restrained motion over complex choreography.
4. Character and environment continuity matter.
5. Build a strong source image before animation.
6. Keep model-specific details out of story JSON where possible.
7. Don't present invented devotional fiction as scripture.
8. Target vertical 9:16 short-form movies first.
9. Optimize for viewer retention, not a fixed shot count.
10. Keep image, video and audio backends replaceable.

## Roadmap

- robust ComfyUI workflow parameter mapping
- reusable master character/environment assets
- Wan 2.2 I2V adapter hardening
- automatic shot rendering/retry/resume
- ACE-Step music adapter
- Sarvam dialogue adapter
- SFX
- FFmpeg assembly
- optional captions
- batch rendering
- story library/metadata
