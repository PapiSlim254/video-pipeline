"""
footage_sourcer.py
------------------
Downloads and organises footage from YouTube and Pexels
into a local library, indexed by niche and keyword.

Usage:
  python footage_sourcer.py --niche "dark_motivation" --keywords "war soldier running" "sword battle" "ancient warrior"
  python footage_sourcer.py --niche "luxury_jewellery" --keywords "gold pendant" "roman sculpture" "molten metal"

Library structure created:
  /footage/
    dark_motivation/
      war_soldier_running/
        clip_001.mp4
        clip_002.mp4
      sword_battle/
        clip_001.mp4
    index.json   ← searchable record of everything downloaded
"""

import os
import json
import argparse
import subprocess
import time
import re
import requests
from pathlib import Path
from datetime import datetime

# ── CONFIG ──────────────────────────────────────────────────────────────────

FOOTAGE_ROOT   = Path("/home/papi/footage")   # change to your preferred path
PEXELS_API_KEY = ""                            # add your free Pexels API key here
MAX_CLIPS_PER_KEYWORD = 5                      # how many clips to pull per keyword
MAX_DURATION_SECS     = 900                    # skip clips longer than this (60s default)
MIN_DURATION_SECS     = 5                      # skip clips shorter than this
VIDEO_FORMAT          = "mp4"
PREFERRED_QUALITY = "best[height<=1080]/best"

# ── INDEX HELPERS ────────────────────────────────────────────────────────────

def load_index(niche_dir: Path) -> dict:
    index_path = niche_dir / "index.json"
    if index_path.exists():
        with open(index_path) as f:
            return json.load(f)
    return {"niche": niche_dir.name, "keywords": {}, "total_clips": 0}

def save_index(niche_dir: Path, index: dict):
    with open(niche_dir / "index.json", "w") as f:
        json.dump(index, f, indent=2)

def slug(text: str) -> str:
    """Convert 'war soldier running' → 'war_soldier_running'"""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")

# ── YOUTUBE SOURCING ─────────────────────────────────────────────────────────

def search_and_download_youtube(keyword: str, dest_dir: Path, max_clips: int) -> list[str]:
    """
    Uses yt-dlp to search YouTube for the keyword and download
    up to max_clips matching videos.
    Returns list of downloaded file paths.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    search_query = f"ytsearch{max_clips}:{keyword} cinematic"

    print(f"  [YouTube] Searching: '{keyword} cinematic'")

    cmd = [
        "yt-dlp", "--cookies-from-browser", "chrome",
        search_query,
        "--format", PREFERRED_QUALITY,
        "--output", str(dest_dir / "%(autonumber)s_%(id)s.%(ext)s"),
        "--no-playlist",
        "--match-filter", f"duration < {MAX_DURATION_SECS} & duration > {MIN_DURATION_SECS}",
        "--max-downloads", str(max_clips),
        "--merge-output-format", "mp4",
        "--quiet",
        "--no-warnings",
        "--write-info-json",   # saves metadata alongside each clip
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0 and result.stderr:
            print(f"  [YouTube] Warning: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print(f"  [YouTube] Timeout on keyword: {keyword}")

    # Collect what was actually downloaded
    downloaded = sorted(dest_dir.glob("*.mp4"))
    print(f"  [YouTube] Downloaded {len(downloaded)} clip(s)")
    return [str(p) for p in downloaded]


# ── PEXELS SOURCING ──────────────────────────────────────────────────────────

def search_and_download_pexels(keyword: str, dest_dir: Path, max_clips: int) -> list[str]:
    """
    Falls back to Pexels free stock video API when no Pexels key is set
    this function is skipped gracefully.
    Returns list of downloaded file paths.
    """
    if not PEXELS_API_KEY:
        print(f"  [Pexels] Skipped — no API key set in PEXELS_API_KEY")
        return []

    dest_dir.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": PEXELS_API_KEY}
    url = "https://api.pexels.com/videos/search"
    params = {"query": keyword, "orientation": "portrait", "per_page": max_clips, "size": "medium"}

    print(f"  [Pexels] Searching: '{keyword}'")

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
    except Exception as e:
        print(f"  [Pexels] Error: {e}")
        return []

    downloaded = []
    for i, video in enumerate(videos):
        # Pick the best quality portrait file
        files = sorted(video.get("video_files", []),
                       key=lambda x: x.get("width", 0), reverse=True)
        portrait = next((f for f in files if (f.get("height", 0) or 0) > (f.get("width", 0) or 0)), files[0] if files else None)
        if not portrait:
            continue

        video_url = portrait.get("link")
        if not video_url:
            continue

        out_path = dest_dir / f"pexels_{i+1:03d}_{video['id']}.mp4"
        if out_path.exists():
            downloaded.append(str(out_path))
            continue

        try:
            r = requests.get(video_url, stream=True, timeout=60)
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            downloaded.append(str(out_path))
            print(f"  [Pexels] Saved: {out_path.name}")
        except Exception as e:
            print(f"  [Pexels] Failed to download clip: {e}")

    print(f"  [Pexels] Downloaded {len(downloaded)} clip(s)")
    return downloaded


# ── GET CLIP DURATION ─────────────────────────────────────────────────────────

def get_duration(filepath: str) -> float:
    """Use ffprobe to get clip duration in seconds."""
    try:
        result = subprocess.run([
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0", filepath
        ], capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except:
        return 0.0


# ── MAIN ──────────────────────────────────────────────────────────────────────

def source_footage(niche: str, keywords: list[str]):
    """
    Main entry point. For each keyword:
    1. Search YouTube → download clips
    2. Search Pexels → download clips (if key set)
    3. Update the niche index.json
    """
    niche_dir = FOOTAGE_ROOT / slug(niche)
    niche_dir.mkdir(parents=True, exist_ok=True)

    index = load_index(niche_dir)
    index["niche"] = niche
    index["last_updated"] = datetime.now().isoformat()

    print(f"\n{'='*55}")
    print(f"  NICHE: {niche}")
    print(f"  DESTINATION: {niche_dir}")
    print(f"{'='*55}\n")

    for keyword in keywords:
        kslug = slug(keyword)
        keyword_dir = niche_dir / kslug
        print(f"── Keyword: '{keyword}'")

        # Skip if already have enough clips
        existing = list(keyword_dir.glob("*.mp4")) if keyword_dir.exists() else []
        if len(existing) >= MAX_CLIPS_PER_KEYWORD:
            print(f"  Already have {len(existing)} clips — skipping\n")
            continue

        needed = MAX_CLIPS_PER_KEYWORD - len(existing)

        # Source from YouTube first
        yt_clips = search_and_download_youtube(keyword, keyword_dir, needed)

        # Fill remaining from Pexels
        still_needed = MAX_CLIPS_PER_KEYWORD - len(list(keyword_dir.glob("*.mp4")))
        px_clips = []
        if still_needed > 0 and PEXELS_API_KEY:
            px_clips = search_and_download_pexels(keyword, keyword_dir, still_needed)

        # Build index entry for this keyword
        all_clips = list(keyword_dir.glob("*.mp4"))
        clip_records = []
        for clip in all_clips:
            duration = get_duration(str(clip))
            clip_records.append({
                "file": str(clip),
                "duration_secs": round(duration, 2),
                "source": "pexels" if "pexels_" in clip.name else "youtube",
                "downloaded_at": datetime.now().isoformat(),
            })

        index["keywords"][kslug] = {
            "original_keyword": keyword,
            "clip_count": len(clip_records),
            "clips": clip_records,
        }
        index["total_clips"] = sum(v["clip_count"] for v in index["keywords"].values())

        save_index(niche_dir, index)
        print(f"  ✓ {len(all_clips)} clips indexed for '{keyword}'\n")
        time.sleep(2)  # be polite between searches

    print(f"\n{'='*55}")
    print(f"  DONE. Total clips in library: {index['total_clips']}")
    print(f"  Index saved to: {niche_dir / 'index.json'}")
    print(f"{'='*55}\n")


# ── QUERY LIBRARY ─────────────────────────────────────────────────────────────

def find_clips(niche: str, keyword: str, max_results: int = 3) -> list[str]:
    """
    Given a niche and keyword, returns a list of matching clip paths.
    Used by the editing pipeline to pull footage for a shot slot.

    Example:
      clips = find_clips("dark_motivation", "war soldier")
      # returns ['/home/papi/footage/dark_motivation/war_soldier/001_abc.mp4', ...]
    """
    niche_dir = FOOTAGE_ROOT / slug(niche)
    if not niche_dir.exists():
        return []

    index = load_index(niche_dir)
    kslug = slug(keyword)

    # Exact match first
    if kslug in index["keywords"]:
        clips = [c["file"] for c in index["keywords"][kslug]["clips"]]
        return clips[:max_results]

    # Fuzzy: find keywords that share words
    keyword_words = set(kslug.split("_"))
    best_match = None
    best_overlap = 0
    for k in index["keywords"]:
        overlap = len(keyword_words & set(k.split("_")))
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = k

    if best_match and best_overlap > 0:
        clips = [c["file"] for c in index["keywords"][best_match]["clips"]]
        return clips[:max_results]

    return []


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Source and organise footage by niche and keyword")
    parser.add_argument("--niche", required=True, help="Niche name e.g. 'dark_motivation' or 'luxury_jewellery'")
    parser.add_argument("--keywords", nargs="+", required=True, help="Keywords to search footage for")
    parser.add_argument("--max", type=int, default=MAX_CLIPS_PER_KEYWORD, help="Max clips per keyword")
    args = parser.parse_args()

    MAX_CLIPS_PER_KEYWORD = args.max
    source_footage(niche=args.niche, keywords=args.keywords)
