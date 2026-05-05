"""
editor.py
---------
Reads brief.json, assembles clips into a final TikTok video.
Applies text overlays, glitch transitions, colour grade, watermark.

Usage:
  python3 editor.py --brief /home/cloud/output/brief.json --output /home/cloud/output/final.mp4
"""

import json
import argparse
import subprocess
import random
import os
from pathlib import Path

# stdlib or installed packages only

FOOTAGE_ROOT = Path("/home/cloud/footage")
MUSIC_ROOT   = Path("/home/cloud/music")
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
    """Find a downloaded clip matching the keyword."""
    niche_dir = FOOTAGE_ROOT / slug(niche)
    index_path = niche_dir / "index.json"
    if not index_path.exists():
        return None
    index = json.loads(index_path.read_text())
    kslug = slug(keyword)
    # Exact match
    if kslug in index["keywords"]:
        clips = index["keywords"][kslug]["clips"]
        if clips:
            return clips[0]["file"]
    # Fuzzy match
    kwords = set(kslug.split("_"))
    for k, v in index["keywords"].items():
        if kwords & set(k.split("_")) and v["clips"]:
            return v["clips"][0]["file"]
    return None

def extract_segment(input_path, duration, output_path):
    """Extract best segment using scenedetect fallback."""
    total = get_duration(input_path)
    max_start = max(0, min(total * 0.4, total - duration - 1))
    start = random.uniform(0, max_start)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(input_path),
        "-t", str(duration),
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT}",
        "-c:v", "libx264", "-c:a", "aac",
        "-loglevel", "error",
        str(output_path)
    ]
    subprocess.run(cmd, timeout=120)

def apply_color_grade(input_path, grade, output_path):
    """Apply colour grade via FFmpeg eq filter."""
    grade_filters = {
        "desaturated":   "eq=saturation=0.3:contrast=1.2:brightness=-0.05",
        "black_and_white": "hue=s=0,eq=contrast=1.3:brightness=-0.05",
        "warm_gold":     "eq=saturation=1.2:contrast=1.1,colorbalance=rs=0.1:gs=0.05:bs=-0.1",
        "high_contrast": "eq=contrast=1.5:brightness=-0.1:saturation=0.5",
        "cold_blue":     "eq=saturation=0.8,colorbalance=rs=-0.1:gs=0:bs=0.15",
        "none":          "null",
    }
    vf = grade_filters.get(grade, "null")
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-c:a", "copy",
        "-loglevel", "error",
        str(output_path)
    ]
    subprocess.run(cmd, timeout=120)

def add_text_overlay(input_path, text, start_time, output_path):
    """Burn bold white text onto the video."""
    if not text or not text.strip():
        import shutil
        shutil.copy(str(input_path), str(output_path))
        return
    safe_text = text.replace("'", "\\'").replace(":", "\\:")
    drawtext = (
        f"drawtext=text='{safe_text}'"
        f":fontfile={FONT_PATH}"
        f":fontsize=48:fontcolor=white"
        f":borderw=3:bordercolor=black"
        f":x=(w-text_w)/2:y=(h-text_h)/2"
        f":enable='between(t,{start_time},{start_time+2.0})'"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", drawtext,
        "-c:v", "libx264", "-c:a", "copy",
        "-loglevel", "error",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        import shutil
        shutil.copy(str(input_path), str(output_path))

def apply_glitch(input_path, output_path):
    """Simple glitch effect using FFmpeg rgbashift + noise."""
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", "rgbashift=rh=5:bh=-5,noise=alls=20:allf=t",
        "-c:v", "libx264", "-c:a", "copy",
        "-loglevel", "error",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        import shutil
        shutil.copy(str(input_path), str(output_path))

def add_watermark(input_path, output_path, text="@pipeline"):
    """Add subtle watermark to top right."""
    drawtext = (
        f"drawtext=text='{text}'"
        f":fontfile={FONT_PATH}"
        f":fontsize=22:fontcolor=white@0.6"
        f":borderw=1:bordercolor=black@0.4"
        f":x=w-text_w-20:y=20"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", drawtext,
        "-c:v", "libx264", "-c:a", "copy",
        "-loglevel", "error",
        str(output_path)
    ]
    subprocess.run(cmd, timeout=120)

def concat_clips(clip_paths, output_path):
    """Concatenate a list of clips into one video."""
    list_file = Path("/tmp/concat_list.txt")
    with open(list_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-c:a", "aac",
        "-loglevel", "error",
        str(output_path)
    ]
    subprocess.run(cmd, timeout=300)

def mix_music(video_path, music_path, output_path):
    """Mix background music under the video audio (or replace if no audio)."""
    if not music_path or not Path(music_path).exists():
        import shutil
        shutil.copy(str(video_path), str(output_path))
        return
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(music_path),
        "-filter_complex",
        "[1:a]volume=0.3[music];[0:a][music]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest",
        "-loglevel", "error",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        import shutil
        shutil.copy(str(video_path), str(output_path))

def find_music(music_mood):
    """Find a music track matching the mood from local library."""
    if not MUSIC_ROOT.exists():
        return None
    mood_dir = MUSIC_ROOT / music_mood
    if mood_dir.exists():
        tracks = list(mood_dir.glob("*.mp3")) + list(mood_dir.glob("*.m4a"))
        if tracks:
            return str(random.choice(tracks))
    # Fallback: any music file
    all_tracks = list(MUSIC_ROOT.rglob("*.mp3")) + list(MUSIC_ROOT.rglob("*.m4a"))
    return str(random.choice(all_tracks)) if all_tracks else None

def assemble(brief_path, output_path):
    brief = json.loads(Path(brief_path).read_text())
    shots = brief["shots"]
    niche = brief["vibe"]["niche"]
    music_mood = brief.get("music_mood", "epic")
    tmp = Path("/tmp/pipeline_edit")
    tmp.mkdir(exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  EDITOR — assembling {len(shots)} shots")
    print(f"  Niche: {niche} | Music: {music_mood}")
    print(f"{'='*55}\n")

    processed_clips = []

    for shot in shots:
        n = shot["shot_number"]
        keyword = shot["footage_keyword"]
        duration = shot["clip_duration_secs"]
        text = shot.get("text_overlay", "")
        text_time = shot.get("text_timing_secs", 0.5)
        transition = shot.get("transition_out", "cut")
        grade = shot.get("color_grade", "none")

        print(f"  Shot {n}: '{keyword}' ({duration}s) text='{text[:20]}'")

        # 1. Find source clip
        source = find_clip(niche, keyword)
        if not source:
            print(f"    ⚠ No clip found for '{keyword}' — skipping")
            continue
        print(f"    Source: {Path(source).name}")

        # 2. Extract segment
        seg_path = tmp / f"{n:02d}_seg.mp4"
        extract_segment(source, duration, seg_path)

        # 3. Colour grade
        graded_path = tmp / f"{n:02d}_graded.mp4"
        apply_color_grade(seg_path, grade, graded_path)

        # 4. Text overlay
        text_path = tmp / f"{n:02d}_text.mp4"
        add_text_overlay(graded_path, text, text_time, text_path)

        # 5. Glitch transition if specified
        if transition == "glitch":
            glitch_path = tmp / f"{n:02d}_glitch.mp4"
            apply_glitch(text_path, glitch_path)
            processed_clips.append(str(glitch_path))
        else:
            processed_clips.append(str(text_path))

        print(f"    ✓ Shot {n} processed")

    if not processed_clips:
        print("  ✗ No clips were processed. Check footage library.")
        return False

    # 6. Concatenate all shots
    print(f"\n  Concatenating {len(processed_clips)} shots...")
    concat_path = tmp / "concat.mp4"
    concat_clips(processed_clips, concat_path)

    # 7. Mix music
    print("  Mixing music...")
    music_file = find_music(music_mood)
    if music_file:
        print(f"  Music: {Path(music_file).name}")
    else:
        print("  No music found — add tracks to /home/cloud/music/epic/")
    music_path = tmp / "with_music.mp4"
    mix_music(concat_path, music_file, music_path)

    # 8. Watermark
    print("  Adding watermark...")
    add_watermark(music_path, output_path)

    print(f"\n  ✓ Final video → {output_path}")
    size_mb = Path(output_path).stat().st_size / (1024*1024)
    print(f"  Size: {size_mb:.1f} MB")
    print(f"{'='*55}\n")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief",  required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    assemble(args.brief, args.output)
