# Kaggle WAN 2.2 I2V handoff

The repository can run the complete story through the bundled ComfyUI WAN 2.2 API workflow after the scene images are already generated.

## 1. Required story layout

For every shot:

`output/<story_id>/scenes/<scene_id>/<shot_id>/source.png`

The runner validates that **all story shots** have a source image before it starts. It does not silently skip missing shots.

## 2. Kaggle setup

Copy the repository to `/kaggle/working/bhagwan-stories` and make sure the WAN models used by `workflows/wan22_i2v_api.json` are installed in the ComfyUI model directories.

Start ComfyUI:

```bash
cd /kaggle/working/ComfyUI
python main.py --listen 0.0.0.0 --port 8188 > /kaggle/working/comfyui.log 2>&1 &
```

Wait until ComfyUI is listening on port 8188.

## 3. Generate the whole story

From the repository root:

```bash
cd /kaggle/working/bhagwan-stories

python generate_movie.py \
  movies/krishna_bell_butter_001/story.json \
  --video-only \
  --video-backend comfyui_wan
```

The bundled `workflows/wan22_i2v_api.json` is used automatically.

This processes the shots in story order — all 20 shots for `krishna_bell_butter_001`.

Each shot uses:

- the shot's `source.png`
- the shot's `video_prompt`
- the shot's `duration`
- `generation.i2v.fps` from the story JSON

The runner calculates the WAN latent frame count from duration and FPS as:

`round(duration * fps) + 1`

For the current story, 3 seconds at 16 FPS produces 49 frames.

## 4. Output

Each completed clip is written to:

`output/<story_id>/scenes/<scene_id>/<shot_id>/shot.mp4`

and copied to:

`output/<story_id>/generated_short_videos/<scene_id>/<shot_id>.mp4`

A final manifest is written to:

`output/<story_id>/manifest.json
`

## 5. Important

The workflow is the API-format workflow already used by the repository. Its runtime mappings are:

- positive prompt: node 6
- negative prompt: node 7 (static workflow negative)
- source image: node 57
- WAN frame length: node 55
- output FPS: node 59

FPS is not hardcoded in the Python video runner. The story controls it.

The runner uploads each source image to ComfyUI before queuing that shot, so the workflow's `LoadImage` node receives the correct current shot instead of a stale filename.

## 6. Optional packaging path

If you only want to prepare files for a separate Kaggle notebook, the existing handoff tool remains available:

```bash
python tools/prepare_kaggle_wan.py \
  output/<story_id> \
  /tmp/<story_id>_wan_kaggle
```
