# Kaggle WAN 2.2 I2V test handoff

This is a deliberately small test path for taking already-generated scene images into the existing Kaggle WAN 2.2 I2V environment.

## 1. Generate the scene locally

Generate the story normally so that each shot has:

`output/<story_id>/scenes/<scene_id>/<shot_id>/source.png`

The scene manifest now also preserves each shot's `video_prompt`.

## 2. Prepare the Kaggle handoff

From the repository root:

```bash
python tools/prepare_kaggle_wan.py \
  output/<story_id> \
  /tmp/<story_id>_wan_kaggle
```

Upload the resulting `/tmp/<story_id>_wan_kaggle` folder to Kaggle as the notebook input dataset.

It contains:

```text
wan_manifest.json
scenes/
  scene_01/
    shot_01/source.png
    shot_02/source.png
  ...
```

## 3. Kaggle test

Your Kaggle WAN notebook should read `wan_manifest.json`, loop over `shots`, and use:

- `image` as the source image
- `video_prompt` as the positive prompt
- `duration` as the requested shot duration

For the first experiment, run **one shot only**. Do not batch the whole story until the first shot is clean.

The expected output structure is:

```text
generated_short_videos/
  scene_01/
    shot_01.mp4
```

Then copy those MP4s back into:

`output/<story_id>/generated_short_videos/<scene_id>/<shot_id>.mp4`

## 4. Important

This change does **not** alter the local ComfyUI WAN adapter. The existing `src/vid/comfyui.py` remains available for local ComfyUI experiments.

The new script only packages the scene images and metadata needed by Kaggle.

## 5. Why this exists

VideoExpress can be tested independently first. If it produces a useful still/frame for a shot, place that image into the corresponding:

`scenes/<scene_id>/<shot_id>/source.png`

slot and use the same Kaggle WAN test. This makes it easy to compare:

- Flux/Qwen scene -> WAN
- VideoExpress frame -> WAN

without changing the WAN generation code.
