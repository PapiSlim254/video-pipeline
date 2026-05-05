# PRD — Automated TikTok Video Production Pipeline

---

## Problem Statement

A video content agency produces short-form TikTok videos for multiple clients across different niches. The current workflow is entirely manual: the editor sources footage from YouTube, assembles clips, adds text overlays, applies colour grades, and delivers to clients. This limits output to a small number of videos per day and creates a bottleneck on the editor's time.

The agency operator (Salim) needs to reduce the editor's workload and increase output capacity without sacrificing quality, so the business can take on more clients and produce more videos per client.

---

## Solution

An automated end-to-end pipeline that takes a structured brief as input and produces a TikTok-ready `.mp4` as output. The pipeline chains five sequential modules: brief generation → footage sourcing → clip selection → video assembly → delivery. The editor's only remaining jobs are writing the brief and reviewing the final video before it goes out.

The pipeline runs on a self-hosted home server (HP ProBook 440 G5, Ubuntu) and is accessible from any machine via a shared GitHub repository. All AI calls are abstracted behind a single provider layer, allowing the LLM to be swapped without touching the pipeline.

---

## User Stories

**Brief Input**

1. As an editor, I want to fill in a short interactive form (niche, audience, tone, hook, style reference, text preference) so that the pipeline has enough context to generate accurate footage keywords and shot structures without me writing a lengthy spec.
2. As an editor, I want the form to accept a one-line hook and expand it into a full structured brief automatically, so I don't need to think about shot counts or timing.
3. As an operator, I want the brief to be saved as a JSON file so I can audit, rerun, or modify it later without re-entering everything.

**Footage Sourcing**

4. As an editor, I want the pipeline to automatically search YouTube using keywords derived from the brief and download matching clips, so I never manually hunt for footage.
5. As an operator, I want downloaded clips to be organised by niche and keyword into a local library with an index file, so clips are reused across videos without re-downloading.
6. As an editor, I want the sourcer to skip keywords that already have enough clips in the library, so the pipeline doesn't waste time or bandwidth re-downloading.
7. As an operator, I want yt-dlp to use browser cookies and a JavaScript runtime automatically, so YouTube's bot detection doesn't block downloads.
8. As an editor, I want the sourcer to fall back to Pexels stock footage when YouTube returns no results for a keyword, so the library is always populated.

**Clip Selection**

9. As an editor, I want the pipeline to automatically find the most visually dynamic segment within a downloaded clip, so shots look intentional rather than randomly cut.
10. As an operator, I want clip selection to fall back to a smart random offset from the first 40% of the video if scene detection fails, so the pipeline never stalls.
11. As an editor, I want every extracted clip to be cropped and scaled to 9:16 automatically, so the output is always TikTok-native without manual reformatting.

**Video Assembly**

12. As an editor, I want the assembler to apply the correct colour grade per shot based on the brief's mood profile, so videos have a consistent cinematic look.
13. As an editor, I want bold centred text overlays to appear on shots that specify text, and no text on shots that don't, so the kinetic typography feels intentional and not cluttered.
14. As an editor, I want glitch transitions to appear only at the start of shots marked as glitch transitions, with subtle chromatic aberration rather than full-frame distortion, so transitions feel stylistic rather than broken.
15. As an editor, I want background music to be mixed at a low volume under the video audio when a track matching the brief's music mood exists in the local library, so videos have atmosphere without manual audio mixing.
16. As an operator, I want a watermark burned into every video automatically, so all outputs are branded before delivery.
17. As an editor, I want the assembler to clean up all temporary files after rendering, so the server doesn't fill up with intermediate clips.

**Delivery**

18. As an operator, I want finished videos saved to a designated output folder, so they are easy to locate and share.
19. As an operator, I want n8n (self-hosted) to watch the output folder and automatically generate a Nextcloud share link and notify the client when a new video appears, so delivery requires no manual steps.
20. As an operator, I want n8n to schedule TikTok posts via the TikTok Content Posting API at pre-configured time slots, so posting is handled without manual intervention.

**Multi-niche Support**

21. As an operator, I want the pipeline to infer the correct niche from the brief form and route footage sourcing and colour grading to the right niche library and template, so the same pipeline handles clients across different content categories.
22. As an editor, I want to be able to run `python3 brief_form.py` once and have everything through to a finished video happen automatically, so my daily workflow is one command plus a review.

---

## Implementation Decisions

**Modules**

- `brief_form.py` — interactive CLI form. Collects 6 fields, enriches them into a full prompt string, hands off to `run_pipeline.py`.
- `brief_engine.py` — calls the AI provider with the enriched prompt. Returns two JSON files: `vibe.json` (mood, energy, colour grade, BPM range, footage keywords) and `brief.json` (shot-by-shot list with keyword, duration, text overlay, transition, colour grade per shot).
- `ai_provider.py` — single abstraction layer for all LLM calls. `ACTIVE_PROVIDER` flag switches between Groq (v1, free) and DeepSeek V3 (v2, cheap). Claude supported as a third option. No other module imports an LLM library directly.
- `footage_sourcer.py` — yt-dlp + Pexels API. Reads keywords from `brief.json`, downloads up to `MAX_CLIPS_PER_KEYWORD` clips per keyword, indexes everything in `footage/{niche}/index.json`. Reads yt-dlp config from `~/.config/yt-dlp/config` for cookies and JS runtime settings.
- `clip_selector.py` — PySceneDetect + FFmpeg. Accepts a source file and target duration, returns a trimmed 9:16 clip extracted from the most dynamic scene.
- `editor.py` — FFmpeg orchestrator. Reads `brief.json`, calls `clip_selector` per shot, applies colour grade, text overlay, glitch transition, concatenates, mixes music, burns watermark.
- `run_pipeline.py` — master runner. Chains `brief_engine` → `footage_sourcer`. Editor is called separately after review.

**Architectural decisions**

- All file paths use the running user's home directory, not hardcoded `/home/cloud`. Both the server (user: cloud) and G14 (user: papi) run the same codebase from the same GitHub repo with paths resolved at runtime.
- No API keys are stored in code. All keys are environment variables set in `~/.bashrc`.
- yt-dlp configuration (cookies, JS runtime, format selector) lives in `~/.config/yt-dlp/config`, not in `footage_sourcer.py`, so the pipeline code is portable without modification.
- Footage libraries are local to each machine and not committed to GitHub. The `footage/`, `output/`, and `music/` directories are gitignored.
- The music library is organised as `/home/{user}/music/{mood}/` where mood matches the `music_mood` field in `brief.json` (e.g. `epic`, `dark_ambient`, `trap_instrumental`).

**AI prompt design**

- Vibe analysis prompt instructs the model to return footage keywords as short 2–4 word YouTube search terms, not poetic descriptions.
- Shot list prompt explicitly forbids "black screen" and transition descriptions as footage keywords.
- Both prompts use `expect_json=True` which appends a JSON-only instruction and strips markdown fences before parsing.

---

## Testing Decisions

**What makes a good test here**

Each module has a clear input/output contract and can be tested in isolation. A good test confirms the contract, not the implementation.

- `brief_engine` — given a script string, returns a dict with required keys (`mood`, `footage_keywords`, `shots`, etc.). Test with a fixed script and assert structure, not specific values (LLM output is non-deterministic).
- `footage_sourcer` — given a niche and keywords, creates the expected directory structure and populates `index.json`. Test with a mock yt-dlp that returns a fixture file instead of downloading.
- `clip_selector` — given an input video and duration, returns an output file of approximately the correct duration in 9:16 format. Use a short test video as fixture.
- `editor` — given a `brief.json` and a footage library with at least one clip per keyword, produces a non-empty `.mp4` of approximately the expected duration. Smoke test only — visual quality is not automatically testable.
- `ai_provider` — given `ACTIVE_PROVIDER = "groq"` and a valid key, returns a non-empty string. Test the provider switch by asserting that changing the flag routes to the correct `_ask_*` function.

**Modules to test first**

`clip_selector` and `editor` have the most failure modes and the clearest contracts. Start there.

---

## Out of Scope

- Beat-matched cuts (planned for v2 — requires librosa BPM detection and beat timestamp extraction)
- Vision-based clip relevance scoring (planned for v2 — send extracted frame to vision model, score against shot description)
- TikTok API posting (n8n handles this — outside the pipeline codebase)
- Client-facing UI or web dashboard
- Multi-user support — pipeline is single-operator
- Audio narration or voiceover — this style has no voiceover
- CapCut or Shotstack integration — FFmpeg handles all editing
- Windows support — pipeline is Linux only

---

## Further Notes

**Assumptions made**

- The editor reviews every video before it posts. There is no fully autonomous posting without human approval at this stage.
- The music library is populated manually by the operator. No automated music sourcing is included in this version.
- The partner (editor) adopts the `brief_form.py` entry point as his daily workflow. If he doesn't, the pipeline still works but won't produce the enriched context that improves footage keyword quality.
- Clients supply product shots for product showcase videos. The pipeline cannot source product-specific imagery automatically.

**Open questions**

- What is the watermark text for each client? Currently hardcoded as `@pipeline` — needs to be a brief form field.
- How does the pipeline handle a niche it has never seen before? First run is slow (downloads everything). Should there be a "seed library" step that pre-populates common niches before a job comes in?
- Does the partner want to approve the `brief.json` shot list before footage is sourced, or does he only review the final video?
- Should failed shots (no clip found) block the whole video or produce a video with fewer shots?

**Known issues at time of writing**

- Text centering is broken in the current deployed editor — text runs to the left edge instead of centering. Fix is in the updated `editor.py` artifact but not yet deployed to the server.
- The pipeline uses a random clip offset for clip selection instead of PySceneDetect — `clip_selector.py` exists but is not yet wired into `editor.py`.
- No music library exists yet — all videos are produced without background audio.
- The `run_pipeline.py` default output path is still hardcoded to `/home/cloud/output` on the server version — needs the runtime path resolution fix applied.
