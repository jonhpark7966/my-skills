#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from srt_utils import normalize_entries, parse_srt, write_srt, write_vtt


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize SRT to single-line cues.")
    parser.add_argument("input", type=Path, help="Input SRT path")
    parser.add_argument("output", type=Path, help="Output SRT path")
    parser.add_argument("--max-chars", type=int, default=42, help="Max characters per cue")
    parser.add_argument("--min-duration", type=float, default=0.8, help="Minimum cue duration (seconds)")
    parser.add_argument("--write-vtt", action="store_true", help="Also write VTT next to output")
    args = parser.parse_args()

    entries = parse_srt(args.input)
    normalized = normalize_entries(entries, max_chars=args.max_chars, min_duration_s=args.min_duration)
    write_srt(normalized, args.output)
    if args.write_vtt:
        write_vtt(normalized, args.output.with_suffix(".vtt"))


if __name__ == "__main__":
    main()
