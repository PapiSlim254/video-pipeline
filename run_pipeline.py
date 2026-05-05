"""
run_pipeline.py
---------------
Master runner. Takes a script, generates the brief,
then immediately sources footage for every shot.

Usage:
  python3 run_pipeline.py --script "Why do men sacrifice everything for honour?"
"""

import json
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/home/cloud")
from brief_engine import run_pipeline
from footage_sourcer import source_footage

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True)
    parser.add_argument("--output", default="/home/cloud/output")
    args = parser.parse_args()

    # Step 1 — Generate brief
    brief = run_pipeline(script=args.script, output_dir=args.output)

    # Step 2 — Extract unique keywords from shot list
    keywords = list({shot["footage_keyword"] for shot in brief["shots"]})
    niche = brief["vibe"]["niche"].replace(" ", "_")

    print(f"\n── Sourcing footage for {len(keywords)} keywords in niche: {niche}")
    print(f"   Keywords: {keywords}\n")

    # Step 3 — Download footage for each keyword
    source_footage(niche=niche, keywords=keywords)

    print("\n✓ Pipeline complete.")
    print(f"  Brief  → {args.output}/brief.json")
    print(f"  Footage → /home/cloud/footage/{niche}/")

if __name__ == "__main__":
    main()
