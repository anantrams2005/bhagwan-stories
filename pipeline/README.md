# Pipeline

All production code for the cinematic devotional movie generator belongs under this directory.

Planned modules:

- story/ — story schema, validation and planning
- generation/ — image/video model adapters
- audio/ — music, dialogue and SFX adapters
- render/ — FFmpeg assembly and post-processing
- assets/ — reusable character/location/prop handling
- cli/ — command-line entry points

Model integrations should remain isolated from story/business logic so a model can be replaced without rewriting the pipeline.

The initial implementation in src/ is retained in this PR only as a bootstrap; it should be migrated into these domain-specific modules before the pipeline grows further.
