import subprocess
import argparse
import random
from pathlib import Path

WIDTH, HEIGHT = 1080, 1920
ENCODE_PRESET = "medium"
ENCODE_CRF = "18"

try:
    from scenedetect import open_video, SceneManager
    from scenedetect.detectors import ContentDetector
    SCENEDETECT_AVAILABLE = True
except ImportError:
    SCENEDETECT_AVAILABLE = False

def get_video_duration(filepath):
    result = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0", filepath
    ], capture_output=True, text=True, timeout=15)
    try:
        return float(result.stdout.strip())
    except:
        return 0.0

def find_best_moment(filepath, target_duration):
    total_duration = get_video_duration(filepath)
    if not SCENEDETECT_AVAILABLE:
        max_start = min(total_duration * 0.33, total_duration - target_duration)
        return random.uniform(0, max(0, max_start))
    try:
        video = open_video(filepath)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=30.0))
        scene_manager.detect_scenes(video, show_progress=False)
        scenes = scene_manager.get_scene_list()
        if not scenes:
            max_start = min(total_duration * 0.33, total_duration - target_duration)
            return random.uniform(0, max(0, max_start))
        best_start = 0.0
        best_score = -1
        for start, end in scenes:
            start_secs = start.get_seconds()
            end_secs = end.get_seconds()
            scene_duration = end_secs - start_secs
            if scene_duration < target_duration:
                continue
            position_penalty = start_secs / total_duration
            score = scene_duration - (position_penalty * 10)
            if score > best_score:
                best_score = score
                best_start = start_secs
        best_start = min(best_start, total_duration - target_duration - 0.5)
        return max(0.0, best_start)
    except Exception as e:
        print(f"  [ClipSelector] SceneDetect failed ({e}), using fallback")
        max_start = min(total_duration * 0.33, total_duration - target_duration)
        return random.uniform(0, max(0, max_start))

def extract_clip(input_path, start_secs, duration, output_path):
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_secs),
        "-i", input_path,
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", ENCODE_PRESET,
        "-crf", ENCODE_CRF,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-movflags", "+faststart",
        "-loglevel", "error",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  [ClipSelector] FFmpeg error: {result.stderr[:200]}")
        return False
    return True

def select_and_extract(input_path, target_duration, output_path):
    print(f"  [ClipSelector] Analysing: {Path(input_path).name}")
    start_secs = find_best_moment(input_path, target_duration)
    print(f"  [ClipSelector] Best moment at {start_secs:.1f}s → extracting {target_duration}s")
    success = extract_clip(input_path, start_secs, target_duration, output_path)
    if success:
        print(f"  [ClipSelector] Saved → {output_path}")
    return success

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",    required=True)
    parser.add_argument("--duration", type=float, default=3.0)
    parser.add_argument("--output",   required=True)
    args = parser.parse_args()
    select_and_extract(args.input, args.duration, args.output)
