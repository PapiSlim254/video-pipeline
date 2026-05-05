"""
editor.py
---------
Reads brief.json, assembles clips into a final TikTok video.
Applies text overlays, glitch transitions, colour grade, watermark.

Usage:
  python3 editor.py --brief /home/papi/output/brief.json --output /home/papi/output/final.mp4
"""

import json
import argparse
import subprocess
import random
import shutil
from pathlib import Path

FOOTAGE_ROOT = Path("/home/papi/footage")
MUSIC_ROOT   = Path("/home/papi/music")
FONT_PATH    = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
WIDTH, HEIGHT = 478, 850

def get_duration(path):
    r = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path)
    ], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except:
        return 0.0

def slug(text):
    import re
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")

def find_clip(niche, keyword):
    niche_dir = FOOTAGE_ROOT / slug(niche)
    index_path = niche_dir / "index.json"
    if not index_path.exists():
        return None
    index = json.loads(index_path.read_text())
    kslug = slug(keyword)
    if kslug in index["keywords"]:
        clips = index["keywords"][kslug]["clips"]
        if clips:
            return clips[0]["file"]
    kwords = set(kslug.split("_"))
    for k, v in index["keywords"].items():
        if kwords & set(k.split("_")) and v["clips"]:
            return v["clips"][0]["file"]
    return None

def extract_segment(input_path, duration, output_path):
    total = get_duration(input_path)
    if total <= 0:
        return False
    # Pick from first 40% of video — avoids credits/end cards
    max_start = max(0, min(total * 0.4, total - duration - 1))
    start = random.uniform(0, max_start)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(input_path),
        "-t", str(duration),
        # Scale to fill 9:16, crop center
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT}",
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        "-r", "30",
        "-loglevel", "error",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.returncode == 0

def apply_color_grade(input_path, grade, output_path):
    # FIX: Lighter grades — don't crush dark footage further
    grade_filters = {
        "desaturated":     "eq=saturation=0.4:contrast=1.1:brightness=0.05",
        "black_and_white": "hue=s=0,eq=contrast=1.2:brightness=0.05",
        "warm_gold":       "eq=saturation=1.3:contrast=1.05,colorbalance=rs=0.1:gs=0.05:bs=-0.1",
        "high_contrast":   "eq=contrast=1.3:brightness=0.02:saturation=0.6",
        "cold_blue":       "eq=saturation=0.7:brightness=0.03,colorbalance=rs=-0.1:gs=0:bs=0.15",
        "none":            "null",
    }
    vf = grade_filters.get(grade, "null")
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        "-loglevel", "error",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        shutil.copy(str(input_path), str(output_path))

def add_text_overlay(input_path, text, output_path):
    # FIX: Text centered properly, appears for full clip duration, no cutoff
    if not text or not text.strip():
        shutil.copy(str(input_path), str(output_path))
        return

    # Escape special chars
    safe_text = (text
        .replace("\\", "\\\\")
        .replace("'", "\u2019")
        .replace(":", "\\:")
        .replace("%", "\\%")
    )

    clip_duration = get_duration(input_path)

    # FIX: Text centered with padding, appears from 0.3s to end-0.3s
    drawtext = (
        f"drawtext="
        f"text='{safe_text}'"
        f":fontfile={FONT_PATH}"
        f":fontsize=44"
        f":fontcolor=white"
        f":borderw=3"
        f":bordercolor=black@0.8"
        f":x=(w-text_w)/2"           # centered horizontally
        f":y=(h-text_h)/2"           # centered vertically
        f":enable='between(t,0.3,{max(0.3, clip_duration - 0.3)})'"
    )

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", drawtext,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        "-loglevel", "error",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"    [Text] Warning: {result.stderr[:100]}")
        shutil.copy(str(input_path), str(output_path))

def apply_glitch(input_path, output_path):
    # FIX: Much subtler glitch — only on first 0.4s of clip
    clip_duration = get_duration(input_path)
    glitch_end = min(0.4, clip_duration * 0.15)

    vf = (
        f"rgbashift=rh=2:bh=-2:enable='lte(t,{glitch_end})',"
        f"noise=alls=8:allf=t:enable='lte(t,{glitch_end})'"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        "-loglevel", "error",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        shutil.copy(str(input_path), str(output_path))

def add_watermark(input_path, output_path, text="@pipeline"):
    safe_text = text.replace("@", "")
    drawtext = (
        f"drawtext="
        f"text='@{safe_text}'"
        f":fontfile={FONT_PATH}"
        f":fontsize=20"
        f":fontcolor=white@0.5"
        f":borderw=1:bordercolor=black@0.3"
        f":x=w-text_w-16:y=16"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", drawtext,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        "-loglevel", "error",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        shutil.copy(str(input_path), str(output_path))

def concat_clips(clip_paths, output_path):
    list_file = Path("/tmp/concat_list.txt")
    with open(list_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac",
        "-loglevel", "error",
        str(output_path)
    ]
    subprocess.run(cmd, timeout=300)

def mix_music(video_path, music_path, output_path):
    if not music_path or not Path(music_path).exists():
        shutil.copy(str(video_path), str(output_path))
        return
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(music_path),
        "-filter_complex",
        "[1:a]volume=0.25[music];[0:a][music]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest",
        "-loglevel", "error",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        shutil.copy(str(video_path), str(output_path))

def find_music(music_mood):
    if not MUSIC_ROOT.exists():
        return None
    mood_dir = MUSIC_ROOT / music_mood
    if mood_dir.exists():
        tracks = list(mood_dir.glob("*.mp3")) + list(mood_dir.glob("*.m4a"))
        if tracks:
            return str(random.choice(tracks))
    all_tracks = list(MUSIC_ROOT.rglob("*.mp3")) + list(MUSIC_ROOT.rglob("*.m4a"))
    return str(random.choice(all_tracks)) if all_tracks else None

def assemble(brief_path, output_path):
    brief = json.loads(Path(brief_path).read_text())
    shots = brief["shots"]
    niche = brief["vibe"]["niche"]
    music_mood = brief.get("music_mood", "epic")
    tmp = Path("/tmp/pipeline_edit")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  EDITOR — {len(shots)} shots | niche: {niche}")
    print(f"{'='*55}\n")

    processed_clips = []

    for shot in shots:
        n          = shot["shot_number"]
        keyword    = shot["footage_keyword"]
        duration   = shot["clip_duration_secs"]
        text       = shot.get("text_overlay", "")
        transition = shot.get("transition_out", "cut")
        grade      = shot.get("color_grade", "none")

        print(f"  Shot {n}: '{keyword}' ({duration}s)", end="")
        if text:
            print(f" | text: '{text[:25]}'", end="")
        print()

        # 1. Find source clip
        source = find_clip(niche, keyword)
        if not source:
            print(f"    ⚠ No clip found — skipping")
            continue

        # 2. Extract segment
        seg_path = tmp / f"{n:02d}_seg.mp4"
        if not extract_segment(source, duration, seg_path):
            print(f"    ⚠ Extraction failed — skipping")
            continue

        # 3. Colour grade
        graded_path = tmp / f"{n:02d}_graded.mp4"
        apply_color_grade(seg_path, grade, graded_path)

        # 4. Text overlay (only if text exists for this shot)
        if text and text.strip():
            text_path = tmp / f"{n:02d}_text.mp4"
            add_text_overlay(graded_path, text, text_path)
        else:
            text_path = graded_path

        # 5. Glitch only on glitch transitions
        if transition == "glitch":
            glitch_path = tmp / f"{n:02d}_final.mp4"
            apply_glitch(text_path, glitch_path)
            processed_clips.append(str(glitch_path))
        else:
            processed_clips.append(str(text_path))

        print(f"    ✓ done")

    if not processed_clips:
        print("  ✗ No clips processed.")
        return False

    # 6. Concatenate
    print(f"\n  Concatenating {len(processed_clips)} shots...")
    concat_path = tmp / "concat.mp4"
    concat_clips(processed_clips, concat_path)

    # 7. Music
    music_file = find_music(music_mood)
    if music_file:
        print(f"  Mixing music: {Path(music_file).name}")
        music_path = tmp / "with_music.mp4"
        mix_music(concat_path, music_file, music_path)
    else:
        print("  No music found — add tracks to /home/papi/music/epic/")
        music_path = concat_path

    # 8. Watermark
    print("  Adding watermark...")
    add_watermark(music_path, output_path)

    size_mb = Path(output_path).stat().st_size / (1024*1024)
    print(f"\n  ✓ Done → {output_path} ({size_mb:.1f} MB)")
    print(f"{'='*55}\n")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief",  required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    assemble(args.brief, args.output)
