# PRD Phase 1: Integrate `clip_selector.py` into `editor.py`

## Problem

`editor.py` currently uses `extract_segment()` with random offsets, while `clip_selector.py` already contains smarter scene-based extraction logic.  
This mismatch causes inconsistent shot quality and weak relevance in final renders.

## Goal

Wire `clip_selector.py` into `editor.py` so shot extraction is scene-aware, deterministic (with seed), and measurable under automated tests.

## Scope (Phase 1 only)

In scope:

- Replace direct `extract_segment()` usage in `editor.py` shot loop with `clip_selector.select_and_extract(...)`.
- Add deterministic seed support to extraction path.
- Add fallback behavior when extraction fails (continue with fallback clip path, not hard fail).
- Add automated acceptance tests and test fixtures/scripts for extraction + assembly contracts.

Out of scope:

- Beat-synced cuts.
- Vision relevance scoring.
- Multi-variant creative ranking.
- Full architecture rewrite or path portability fixes unrelated to clip extraction.

## User stories

1. As an operator, I want clip selection to prioritize dynamic scenes so output feels intentional.
2. As an operator, I want deterministic runs with a fixed seed so I can reproduce outputs.
3. As an editor, I want failed extractions to use fallback behavior so one bad shot does not kill throughput.
4. As an operator, I want automated tests proving the extraction and assembly contracts before merge.

## Functional requirements

1. `editor.py` must call `clip_selector.select_and_extract(source, duration, out_path)` for each shot.
2. If `select_and_extract` fails, editor must use fallback extraction logic and continue.
3. Pipeline must support deterministic mode via seed (CLI arg and/or env), affecting random fallback paths.
4. Editor must preserve existing downstream effects: color grade, text overlay, glitch, concat, music, watermark.
5. Production mode must require SceneDetect availability; missing dependency should raise a clear actionable error.

## Non-functional requirements

- Maintain current runtime profile as much as practical for first implementation.
- Keep CLI behavior backward compatible where possible.
- Keep logs clear for each shot path:
  - `scene_select_success`
  - `scene_select_failed_fallback_used`
  - `shot_skipped` (only if both primary and fallback fail)

## Acceptance criteria (measurable)

1. **Shot success rate gate**
   - For a valid brief with available source clips, final render contains `>= 90%` of planned shots.

2. **Determinism gate**
   - Given same brief, same source media, and same seed, selected clip starts are identical across runs.

3. **Fallback gate**
   - If scene selection fails for a shot, fallback extraction executes and shot is still included when possible.

4. **SceneDetect production gate**
   - In production mode, if SceneDetect is unavailable, run fails fast with explicit remediation instructions.

5. **Media contract gate**
   - Final output is non-empty `.mp4` with expected dimensions (`478x850`) and valid A/V streams.

6. **Duration gate**
   - Duration checks must be explicit in tests and tied to extraction mode/fixtures.
   - Since tolerance is clip-dependent, each test must declare its tolerance bound.

## Proposed implementation plan

1. **Editor integration**
   - Import `select_and_extract` from `clip_selector.py`.
   - Swap shot extraction call in `assemble()` from `extract_segment(...)` to `select_and_extract(...)`.

2. **Deterministic seed**
   - Add `--seed` to `editor.py` CLI and seed `random`.
   - Ensure fallback path uses seeded randomness only.

3. **Fallback path**
   - Keep current `extract_segment()` as fallback implementation.
   - Call fallback only when `select_and_extract(...)` returns false.

4. **SceneDetect policy**
   - Add production-mode check (CLI flag or env, documented clearly).
   - In production mode: if SceneDetect missing, fail before processing shots.

5. **Testing**
   - Add automated tests for:
     - Deterministic selection with seed.
     - Fallback execution on selector failure.
     - End-to-end smoke assembly contract on fixture media.
   - Add helper scripts/fixtures for reproducible ffmpeg/ffprobe assertions.

## Test plan

Automated:

- `test_clip_selector_determinism`
- `test_editor_uses_clip_selector_before_fallback`
- `test_editor_fallback_on_selector_failure`
- `test_editor_output_contract` (dimensions, non-empty file, stream presence)

Smoke:

- Run editor on a real `brief.json` + local footage index.
- Verify logs show selection path per shot.
- Verify final output plays and meets expected quality bar.

## Risks and mitigations

- **Risk:** SceneDetect failures on noisy/low-motion footage.  
  **Mitigation:** keep robust fallback extraction and explicit logging.

- **Risk:** Runtime increase due to scene analysis.  
  **Mitigation:** benchmark Phase 1 and tune detector threshold later.

- **Risk:** Determinism drift across environments.  
  **Mitigation:** seed random path and document version constraints for ffmpeg/scenedetect.

## Definition of done

- `editor.py` extraction path is integrated with `clip_selector.py`.
- Deterministic seed option exists and is documented.
- Fallback behavior is implemented and validated.
- Automated tests pass locally for acceptance criteria above.
- Documentation updated (this PRD + execution contract references).
