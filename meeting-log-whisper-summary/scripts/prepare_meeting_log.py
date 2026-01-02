#!/usr/bin/env python3
"""
Prepare a date-based meeting log folder and run Whisper transcription.
"""

import argparse
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def extract_date(value):
    if not value:
        return None
    match_8 = re.search(r"\d{8}", value)
    if match_8:
        return match_8.group(0)
    match_6 = re.search(r"\d{6}", value)
    if match_6:
        return match_6.group(0)
    return None


def resolve_date(notes_path, audio_path, explicit_date):
    if explicit_date:
        return explicit_date
    return (
        extract_date(notes_path.stem)
        or extract_date(audio_path.stem)
        or extract_date(notes_path.name)
        or extract_date(audio_path.name)
    )


def resolve_root(notes_path, date_str, root_override):
    if root_override:
        return Path(root_override).expanduser().resolve()

    root = notes_path.parent
    # Notes might live inside the date directory already.
    if date_str and root.name == date_str:
        root = root.parent
    return root.resolve()


def ensure_dir(path, dry_run):
    if dry_run:
        print(f"[dry-run] mkdir -p {path}")
        return
    path.mkdir(parents=True, exist_ok=True)


def place_audio(audio_path, target_audio, mode, force, dry_run):
    if audio_path.resolve() == target_audio.resolve():
        print(f"Audio already in place: {target_audio}")
        return

    if target_audio.exists() and not force:
        print(f"Target audio exists; keeping: {target_audio}")
        return

    action = "move" if mode == "move" else "copy"
    if dry_run:
        print(f"[dry-run] {action} {audio_path} -> {target_audio}")
        return

    if mode == "move":
        shutil.move(str(audio_path), str(target_audio))
    else:
        shutil.copy2(audio_path, target_audio)


def run_whisper(
    whisper_cmd,
    audio_path,
    output_dir,
    model,
    language,
    task,
    extra_args,
    dry_run,
):
    if dry_run:
        print("[dry-run] whisper command would run")
        return

    if not shutil.which(whisper_cmd):
        raise RuntimeError(
            f"Whisper command not found: {whisper_cmd}. "
            "Install whisper or pass --whisper-cmd."
        )

    cmd = [
        whisper_cmd,
        str(audio_path),
        "--output_dir",
        str(output_dir),
        "--output_format",
        "srt",
        "--model",
        model,
        "--task",
        task,
    ]
    if language:
        cmd += ["--language", language]
    if extra_args:
        cmd += shlex.split(extra_args)

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Whisper failed with exit code {result.returncode}")


def main():
    parser = argparse.ArgumentParser(
        description="Prepare meeting log folder and generate SRT with Whisper."
    )
    parser.add_argument("--notes", required=True, help="Path to notes markdown file")
    parser.add_argument("--audio", required=True, help="Path to audio file (.m4a, etc)")
    parser.add_argument("--date", help="Override date (YYMMDD or YYYYMMDD)")
    parser.add_argument(
        "--meeting-logs-root",
        help="Override meeting_logs root (defaults to notes parent)",
    )
    parser.add_argument(
        "--mode",
        choices=["copy", "move"],
        default="copy",
        help="Copy or move audio into the date folder",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite outputs")
    parser.add_argument(
        "--no-whisper",
        action="store_true",
        help="Skip whisper transcription",
    )
    parser.add_argument(
        "--whisper-cmd",
        default="whisper",
        help="Whisper CLI command name/path",
    )
    parser.add_argument("--model", default="medium", help="Whisper model")
    parser.add_argument("--language", default="ko", help="Whisper language")
    parser.add_argument("--task", default="transcribe", help="Whisper task")
    parser.add_argument(
        "--extra-whisper-args",
        default="",
        help="Extra arguments to append to whisper command",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without modifying files",
    )

    args = parser.parse_args()

    notes_path = Path(args.notes).expanduser().resolve()
    audio_path = Path(args.audio).expanduser().resolve()

    if not notes_path.exists():
        print(f"[error] Notes file not found: {notes_path}")
        sys.exit(1)
    if not audio_path.exists():
        print(f"[error] Audio file not found: {audio_path}")
        sys.exit(1)

    date_str = resolve_date(notes_path, audio_path, args.date)
    if not date_str:
        print("[error] Could not infer date; pass --date explicitly.")
        sys.exit(1)

    root = resolve_root(notes_path, date_str, args.meeting_logs_root)
    output_dir = root / date_str
    target_audio = output_dir / f"{date_str}{audio_path.suffix}"
    target_srt = output_dir / f"{date_str}.srt"

    print("Meeting log root:", root)
    print("Date:", date_str)
    print("Output dir:", output_dir)
    print("Target audio:", target_audio)

    ensure_dir(output_dir, args.dry_run)
    place_audio(audio_path, target_audio, args.mode, args.force, args.dry_run)

    if not args.dry_run and not target_audio.exists():
        print(f"[error] Target audio missing after placement: {target_audio}")
        sys.exit(1)

    if args.no_whisper:
        print("Skipping whisper transcription (--no-whisper)")
        return

    if target_srt.exists() and not args.force:
        print(f"SRT already exists; skipping: {target_srt}")
        return

    try:
        run_whisper(
            args.whisper_cmd,
            target_audio,
            output_dir,
            args.model,
            args.language,
            args.task,
            args.extra_whisper_args,
            args.dry_run,
        )
    except RuntimeError as exc:
        print(f"[error] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
