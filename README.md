# Bhagwan Stories — Cinematic Devotional Movie Pipeline

A Python-first pipeline for turning Indian mythology and devotional stories into short-form cinematic 3D mini-movies.

The goal is **story-first visual filmmaking**, not documentary narration or slideshow reels.

## Pipeline

```
Story JSON
  ↓
Asset planner / reuse existing assets
  ↓
Z-Turbo reusable assets
  ↓
FLUX.2 Klein 4B Image Edit scene source images (16:9)
  ↓
Image-to-video
  ↓
Audio
  ↓
Final edit / delivery format
```

## Image generation split

- **Reusable assets:** Z-Turbo. Characters, village people, children, animals, locations and props are generated only when the asset library does not already contain the requested reference.
- **Scene composition:** FLUX.2 Klein 4B Image Edit using the three active reference-image inputs from the production workflow.
- The Klein workflow uses its reference image size to drive output dimensions through its existing `GetImageSize` path. Therefore the scene source is **16:9 when the reference image supplied to that path is 16:9**.
- The current production scene workflow is the user's ComfyUI Klein 4B Image Edit workflow; the repository adapter does not replace its graph or invent a different reference topology.
- Up to three reusable asset references can be supplied to a shot.

## Requirements

- Python 3.10+
- running ComfyUI
- exported API-compatible ComfyUI workflows
- Z-Turbo workflow for asset generation
- FLUX.2 Klein 4B Image Edit workflow for scene generation

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

Create a production plan:

```bash
python generate_movie.py stories/examples/krishna_flute.json --plan
```

Generate the image stages:

```bash
python generate_movie.py stories/examples/krishna_flute.json \
  --image-backend comfyui \
  --comfyui-url http://127.0.0.1:8188 \
  --asset-image-workflow workflows/z_turbo_assets.json \
  --scene-image-workflow workflows/flux2_klein_4b_scene.json
```

Add I2V:

```bash
python generate_movie.py stories/examples/krishna_flute.json \
  --image-backend comfyui \
  --asset-image-workflow workflows/z_turbo_assets.json \
  --scene-image-workflow workflows/flux2_klein_4b_scene.json \
  --video-backend comfyui_wan \
  --video-workflow workflows/wan_i2v_workflow.json
```

The workflow files stay external so model-specific ComfyUI graphs can evolve without changing story JSON.

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
