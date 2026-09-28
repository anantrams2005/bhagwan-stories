# Z-Turbo Story Scene Experiment

This is a deliberately separate experiment from the asset + FLUX.2 Klein pipeline.

## Goal

Generate **every story scene directly with Z-Image-Turbo / Z-Turbo text-to-image**:

- no reusable asset images
- no 3-reference scene composition
- one fixed seed for the whole story
- one fixed visual bible and recurring cast description injected into every shot
- 16:9 cinematic 3D composition
- grandparent + children storytelling can continue across shots
- each shot is still a complete story frame, not an asset render

### Important

A fixed seed does **not** create true character identity locking. It gives deterministic sampling, but changing the prompt changes the result. The experiment therefore combines the fixed seed with a very explicit recurring cast bible.

If this produces more coherent scenes than the current Klein pipeline, it is a useful indication that a simpler text-to-image pipeline is a better fit for these stories.

## Setup

1. Export your working **API-format** Z-Turbo/Z-Image-Turbo ComfyUI workflow.
2. Put it at:

```
workflows/z_turbo_scene_api.json
```

3. Configure the node IDs in `config.json`. If your workflow contains the `_pipeline_nodes` metadata used by the main repo, those mappings can be used automatically.
4. Install:

```bash
pip install -r requirements.txt
```

5. Start ComfyUI and run:

```bash
python generate_scenes.py stories/krishna_bell_butter.json
```

Output:

```
output/<story_id>/
  scene_01/shot_01.png
  scene_01/shot_02.png
  ...
  manifest.json
```

## Seed strategy

The default demo uses one seed for **all shots**.

Do not expect identical faces in every frame just because the seed is identical. The real test is whether the overall visual world, proportions, clothing and cast remain coherent enough to feel like one animated movie.

For a second story, simply choose another story-level seed.


## Test stories

The experiment now contains the real production story structures:

- `krishna_bell_butter.json` — bell + makkhan story
- `radha_yamuna_boat.json` — Radha/Krishna/Yamuna boat story
- `krishna_brahma_pastime_part1.json` — Brahma pastime Part 1
- `krishna_brahma_pastime_part2.json` — Brahma pastime Part 2

Fixed seeds:

- Bell: **274913**
- Radha/Yamuna: **481207**
- Brahma Part 1 + Part 2: **639821** (same seed deliberately)

Run all four:

```bash
for story in \
  stories/krishna_bell_butter.json \
  stories/radha_yamuna_boat.json \
  stories/krishna_brahma_pastime_part1.json \
  stories/krishna_brahma_pastime_part2.json
do
  python generate_scenes.py "$story"
done
```

The generator uses the original story's `action`, `camera`, scene purpose and referenced character/location descriptions. It intentionally ignores the old FLUX/Klein `image_prompt` so those reference-composition instructions cannot distort this experiment.
