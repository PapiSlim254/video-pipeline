"""
brief_engine.py
---------------
Takes a script or 1-line brief and produces:
  1. A vibe profile
  2. A shot-by-shot video brief

Usage:
  python3 brief_engine.py --script "Why do men sacrifice everything for honour?"
"""

import json
import argparse
from pathlib import Path
from ai_provider import ask_json

VIBE_SYSTEM = """
You are a video creative director specialising in short-form TikTok content.
Analyse a script and return a structured vibe profile as JSON only.
No markdown, no explanation.
"""

VIBE_USER = """
Analyse this script and return this exact JSON:

{{
  "mood": "dark|intense|calm|reflective|hype|luxury|raw",
  "energy": "low|medium|high",
  "color_grade": "desaturated|warm_gold|cold_blue|black_and_white|high_contrast",
  "cut_pace": "slow|medium|fast",
  "bpm_range": [100, 140],
  "footage_keywords": [
    "short 2-4 word YouTube search term",
    "short 2-4 word YouTube search term",
    "short 2-4 word YouTube search term",
    "short 2-4 word YouTube search term",
    "short 2-4 word YouTube search term"
  ],
  "music_mood": "epic|dark_ambient|trap_instrumental|orchestral|lo_fi",
  "text_style": "kinetic_bold|minimal_fade|none",
  "niche": "2-3 word niche e.g. dark_motivation or luxury_jewellery"
}}

IMPORTANT for footage_keywords:
- Keep each keyword 2-4 words maximum
- Use terms that actually exist as YouTube videos
- Think like a YouTube searcher not a poet
- Good examples: "roman soldiers battle", "medieval sword fight", "ancient warrior helmet"
- Bad examples: "honour ritual with ancient warriors", "black screen", "dramatic solo shot"

Script: {script}
"""

BRIEF_SYSTEM = """
You are a video editor building a shot-by-shot assembly brief for a TikTok video.
Return JSON only. No markdown, no explanation.
"""

BRIEF_USER = """
Build a shot list for an automated TikTok editor.

Vibe Profile:
{vibe}

Script:
{script}

Rules:
- Total duration 20-30 seconds
- 5-8 shots, each 2-5 seconds
- footage_keyword must be a simple 2-4 word YouTube search term
- NEVER use "black screen" or transition descriptions as footage keywords
- footage_keyword must describe real video footage that exists on YouTube
- First shot is most dramatic, last shot is strongest visual close

Return this exact JSON:

{{
  "total_duration_secs": 28,
  "video_type": "content_hook",
  "shots": [
    {{
      "shot_number": 1,
      "footage_keyword": "simple youtube search term",
      "clip_duration_secs": 3,
      "text_overlay": "TEXT HERE",
      "text_timing_secs": 0.5,
      "transition_out": "glitch",
      "color_grade": "desaturated",
      "notes": ""
    }}
  ],
  "music_mood": "epic",
  "watermark": true
}}
"""

def analyse_vibe(script):
    print("  [Brief Engine] Analysing vibe...")
    result = ask_json(VIBE_SYSTEM, VIBE_USER.format(script=script))
    return result

def build_shot_list(script, vibe):
    print("  [Brief Engine] Building shot list...")
    result = ask_json(BRIEF_SYSTEM, BRIEF_USER.format(
        vibe=json.dumps(vibe, indent=2),
        script=script
    ))
    return result

def run_pipeline(script, output_dir="."):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  BRIEF ENGINE")
    print(f"  Script: {script[:60]}...")
    print(f"{'='*55}\n")

    vibe = analyse_vibe(script)
    vibe_path = out / "vibe.json"
    with open(vibe_path, "w") as f:
        json.dump(vibe, f, indent=2)
    print(f"  ✓ Vibe saved → {vibe_path}")
    print(f"    Mood: {vibe.get('mood')} | Energy: {vibe.get('energy')} | Niche: {vibe.get('niche')}")
    print(f"    Keywords: {', '.join(vibe.get('footage_keywords', []))}\n")

    brief = build_shot_list(script, vibe)
    brief["script"] = script
    brief["vibe"] = vibe
    brief_path = out / "brief.json"
    with open(brief_path, "w") as f:
        json.dump(brief, f, indent=2)
    print(f"  ✓ Brief saved → {brief_path}")
    print(f"    Shots: {len(brief.get('shots', []))} | Duration: {brief.get('total_duration_secs')}s\n")

    print("  SHOT LIST:")
    for shot in brief.get("shots", []):
        print(f"    [{shot['shot_number']}] {shot['footage_keyword'][:35]:<35} | "
              f"{shot['clip_duration_secs']}s | "
              f"Text: {str(shot.get('text_overlay',''))[:20]:<20} | "
              f"→ {shot['transition_out']}")

    print(f"\n{'='*55}\n")
    return brief

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=str)
    parser.add_argument("--file", type=str)
    parser.add_argument("--output", type=str, default="./output")
    args = parser.parse_args()

    if args.file:
        script = Path(args.file).read_text().strip()
    elif args.script:
        script = args.script
    else:
        print("Provide --script or --file")
        exit(1)

    run_pipeline(script=script, output_dir=args.output)
