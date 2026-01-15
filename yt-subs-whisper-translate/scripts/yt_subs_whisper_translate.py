#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from srt_utils import normalize_entries, parse_srt, write_srt, write_vtt


def _require_exe(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required executable not found in PATH: {name}")
    return path


def _run(cmd: list[str], capture: bool = False) -> str:
    if capture:
        proc = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return proc.stdout
    subprocess.run(cmd, check=True)
    return ""


def _yt_dlp_id(url: str) -> str:
    _require_exe("yt-dlp")
    out = _run(
        ["yt-dlp", "--no-playlist", "--quiet", "--no-warnings", "--print", "%(id)s", "--skip-download", url],
        capture=True,
    )
    video_id = out.strip().splitlines()[-1].strip()
    if not video_id:
        raise RuntimeError("Failed to resolve YouTube video id")
    return video_id


def _yt_dlp_meta(url: str, output_path: Path) -> dict:
    _require_exe("yt-dlp")
    out = _run(
        ["yt-dlp", "--no-playlist", "--quiet", "--no-warnings", "--dump-json", "--skip-download", url],
        capture=True,
    )
    output_path.write_text(out, encoding="utf-8")
    return json.loads(out)


def _select_manual_langs(subtitles: dict) -> tuple[str | None, list[str], list[str]]:
    langs = set(subtitles.keys())
    en_langs = sorted([lang for lang in langs if lang == "en" or lang.startswith("en-")])
    ko_langs = sorted([lang for lang in langs if lang == "ko" or lang.startswith("ko-")])
    zh_langs = sorted([lang for lang in langs if lang.startswith("zh")])

    if zh_langs:
        preferred = "zh-Hans" if "zh-Hans" in zh_langs else "zh-Hant" if "zh-Hant" in zh_langs else zh_langs[0]
        return "zh", [preferred], ["en", "ko"]
    if en_langs and ko_langs:
        en_pref = "en" if "en" in en_langs else en_langs[0]
        ko_pref = "ko" if "ko" in ko_langs else ko_langs[0]
        return None, [en_pref, ko_pref], []
    if en_langs:
        en_pref = "en" if "en" in en_langs else en_langs[0]
        return "en", [en_pref], ["ko"]
    if ko_langs:
        ko_pref = "ko" if "ko" in ko_langs else ko_langs[0]
        return "ko", [ko_pref], []
    return None, [], []


def _download_manual_subs(url: str, out_dir: Path, video_id: str, langs: list[str]) -> list[Path]:
    if not langs:
        return []
    _require_exe("yt-dlp")
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--skip-download",
        "--write-subs",
        "--sub-format",
        "srt",
        "--sub-lang",
        ",".join(langs),
        "-o",
        str(out_dir / f"{video_id}.%(ext)s"),
        url,
    ]
    _run(cmd)

    downloaded: list[Path] = []
    for lang in langs:
        matches = sorted(out_dir.glob(f"{video_id}.{lang}*.srt"))
        if matches:
            downloaded.append(matches[0])
    return downloaded


def _download_audio(url: str, out_dir: Path, video_id: str) -> Path:
    _require_exe("yt-dlp")
    out_dir.mkdir(parents=True, exist_ok=True)
    template = str(out_dir / f"{video_id}.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-x",
        "--audio-format",
        "mp3",
        "-o",
        template,
        url,
    ]
    _run(cmd)
    audio_path = out_dir / f"{video_id}.mp3"
    if not audio_path.exists():
        raise RuntimeError(f"Audio download finished but {audio_path} not found")
    return audio_path


def _whisper_transcribe(audio_path: Path, out_dir: Path, model: str, language: str | None) -> Path:
    _require_exe("whisper")
    out_dir.mkdir(parents=True, exist_ok=True)
    srt_path = out_dir / f"{audio_path.stem}.srt"
    if srt_path.exists():
        return srt_path
    cmd = [
        "whisper",
        str(audio_path),
        "--output_dir",
        str(out_dir),
        "--output_format",
        "srt",
        "--model",
        model,
    ]
    if language:
        cmd.extend(["--language", language])
    _run(cmd)
    if not srt_path.exists():
        raise RuntimeError(f"Whisper finished but SRT not found: {srt_path}")
    return srt_path


def _detect_language(entries: list) -> str:
    counts = {"ko": 0, "zh": 0, "en": 0}
    for entry in entries:
        for ch in entry.text:
            code = ord(ch)
            if 0xAC00 <= code <= 0xD7A3:
                counts["ko"] += 1
            elif 0x4E00 <= code <= 0x9FFF:
                counts["zh"] += 1
            elif "A" <= ch <= "Z" or "a" <= ch <= "z":
                counts["en"] += 1
    if counts["ko"] >= max(counts["zh"], counts["en"]):
        return "ko"
    if counts["zh"] >= counts["en"]:
        return "zh"
    return "en"


def _normalize_file(path: Path, max_chars: int, min_duration: float) -> None:
    entries = parse_srt(path)
    normalized = normalize_entries(entries, max_chars=max_chars, min_duration_s=min_duration)
    write_srt(normalized, path)
    write_vtt(normalized, path.with_suffix(".vtt"))


def _run_translate(
    script_path: Path,
    input_srt: Path,
    output_srt: Path,
    meta_path: Path,
    source_lang: str,
    target_lang: str,
    extra_context: Path | None,
    chunk_seconds: float,
    overlap_seconds: float,
    max_workers: int,
    chunk_model: str,
    chunk_reasoning: str,
    merge_model: str,
    merge_reasoning: str,
    merge_chunk_seconds: float,
    merge_overlap_seconds: float,
    merge_workers: int,
    merge_pass: bool,
    max_chars: int,
    min_duration: float,
    dry_run: bool,
) -> None:
    cmd = [
        sys.executable,
        str(script_path),
        "--input",
        str(input_srt),
        "--output",
        str(output_srt),
        "--meta",
        str(meta_path),
        "--source-lang",
        source_lang,
        "--target-lang",
        target_lang,
        "--chunk-seconds",
        str(chunk_seconds),
        "--overlap-seconds",
        str(overlap_seconds),
        "--max-workers",
        str(max_workers),
        "--chunk-model",
        chunk_model,
        "--chunk-reasoning",
        chunk_reasoning,
        "--merge-model",
        merge_model,
        "--merge-reasoning",
        merge_reasoning,
        "--merge-chunk-seconds",
        str(merge_chunk_seconds),
        "--merge-overlap-seconds",
        str(merge_overlap_seconds),
        "--merge-workers",
        str(merge_workers),
        "--max-chars",
        str(max_chars),
        "--min-duration",
        str(min_duration),
        "--write-vtt",
    ]
    if extra_context:
        cmd.extend(["--extra-context", str(extra_context)])
    if not merge_pass:
        cmd.append("--no-merge-pass")
    if dry_run:
        cmd.append("--dry-run")
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch manual subs, run Whisper fallback, translate with Codex.")
    parser.add_argument("url", nargs="?", help="YouTube URL")
    parser.add_argument("--out-dir", type=Path, help="Output directory")
    parser.add_argument("--meta", type=Path, help="Existing metadata JSON (skip yt-dlp)")
    parser.add_argument("--source-srt", type=Path, help="Use an existing source SRT (skip yt-dlp/whisper)")
    parser.add_argument("--source-lang", help="Override detected source language")
    parser.add_argument("--whisper-language", help="Whisper language hint")
    parser.add_argument("--model", default="turbo", help="Whisper model")
    parser.add_argument("--chunk-seconds", type=float, default=180.0, help="Chunk size in seconds")
    parser.add_argument("--overlap-seconds", type=float, default=30.0, help="Chunk overlap in seconds")
    parser.add_argument("--max-workers", type=int, default=20, help="Parallel workers")
    parser.add_argument("--chunk-model", default="gpt-5.2", help="Codex model for chunk translation")
    parser.add_argument("--chunk-reasoning", default="medium", help="Reasoning effort for chunk translation")
    parser.add_argument("--merge-model", default="gpt-5.2", help="Codex model for merge/repair")
    parser.add_argument("--merge-reasoning", default="high", help="Reasoning effort for merge/repair")
    parser.add_argument("--merge-chunk-seconds", type=float, default=300.0, help="Merge chunk size in seconds")
    parser.add_argument("--merge-overlap-seconds", type=float, default=60.0, help="Merge overlap in seconds")
    parser.add_argument("--merge-workers", type=int, default=4, help="Parallel workers for merge/repair")
    parser.add_argument("--merge-pass", dest="merge_pass", action="store_true", default=True, help="Enable merge/repair")
    parser.add_argument("--no-merge-pass", dest="merge_pass", action="store_false", help="Disable merge/repair")
    parser.add_argument("--max-chars", type=int, default=42, help="Max characters per cue")
    parser.add_argument("--min-duration", type=float, default=0.8, help="Minimum cue duration (seconds)")
    parser.add_argument("--extra-context", type=Path, help="Extra context text for translation")
    parser.add_argument("--dry-run", action="store_true", help="Skip Codex calls; echo input")
    args = parser.parse_args()

    if not args.url and not args.source_srt:
        parser.error("Provide a URL or --source-srt")

    if args.source_srt and not args.source_srt.exists():
        raise RuntimeError(f"Source SRT not found: {args.source_srt}")

    if args.source_srt and not args.out_dir:
        parser.error("--out-dir is required when using --source-srt")

    video_id = None
    meta_path = args.meta
    meta = {}

    if args.source_srt:
        out_dir = args.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        source_srt = args.source_srt
    else:
        if not args.url:
            parser.error("URL is required when not using --source-srt")
        video_id = _yt_dlp_id(args.url)
        out_dir = args.out_dir or Path("yt_subs") / video_id
        out_dir.mkdir(parents=True, exist_ok=True)
        meta_path = meta_path or (out_dir / "meta.json")
        meta = _yt_dlp_meta(args.url, meta_path)

    if meta_path and meta_path.exists() and not meta:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    translate_script = Path(__file__).resolve().parent / "translate_srt_codex.py"

    if args.source_srt:
        source_lang = args.source_lang or _detect_language(parse_srt(source_srt))
        source_srt_path = out_dir / f"{source_lang}.srt"
        source_srt_path.write_text(source_srt.read_text(encoding="utf-8"), encoding="utf-8")
        _normalize_file(source_srt_path, args.max_chars, args.min_duration)

        targets = []
        if source_lang == "en":
            targets = ["ko"]
        elif source_lang == "zh":
            targets = ["en", "ko"]

        for target in targets:
            output_srt = out_dir / f"{target}.srt"
            _run_translate(
                translate_script,
                source_srt_path,
                output_srt,
                meta_path or Path("/dev/null"),
                source_lang,
                target,
                args.extra_context,
                args.chunk_seconds,
                args.overlap_seconds,
                args.max_workers,
                args.chunk_model,
                args.chunk_reasoning,
                args.merge_model,
                args.merge_reasoning,
                args.merge_chunk_seconds,
                args.merge_overlap_seconds,
                args.merge_workers,
                args.merge_pass,
                args.max_chars,
                args.min_duration,
                args.dry_run,
            )
        return

    subtitles = meta.get("subtitles", {})
    source_lang, manual_langs, targets = _select_manual_langs(subtitles)

    downloaded_subs: list[Path] = []
    if manual_langs:
        downloaded_subs = _download_manual_subs(args.url, out_dir, video_id, manual_langs)

    if downloaded_subs:
        for lang in manual_langs:
            matches = sorted(out_dir.glob(f"{video_id}.{lang}*.srt"))
            if not matches:
                continue
            short_lang = "zh" if lang.startswith("zh") else lang.split("-")[0]
            target_path = out_dir / f"{short_lang}.srt"
            target_path.write_text(matches[0].read_text(encoding="utf-8"), encoding="utf-8")
            _normalize_file(target_path, args.max_chars, args.min_duration)
    else:
        source_srt_path = out_dir / "source.srt"
        if not source_srt_path.exists():
            candidate_whisper = out_dir / f"{video_id}.srt"
            if candidate_whisper.exists():
                source_srt_path.write_text(candidate_whisper.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                audio_path = _download_audio(args.url, out_dir, video_id)
                whisper_srt = _whisper_transcribe(audio_path, out_dir, args.model, args.whisper_language)
                source_srt_path.write_text(whisper_srt.read_text(encoding="utf-8"), encoding="utf-8")
        _normalize_file(source_srt_path, args.max_chars, args.min_duration)
        if args.source_lang:
            source_lang = args.source_lang
        elif args.whisper_language:
            source_lang = args.whisper_language
        else:
            source_lang = _detect_language(parse_srt(source_srt_path))
        lang_srt_path = out_dir / f"{source_lang}.srt"
        if not lang_srt_path.exists():
            shutil.copyfile(source_srt_path, lang_srt_path)
            source_vtt_path = source_srt_path.with_suffix(".vtt")
            lang_vtt_path = out_dir / f"{source_lang}.vtt"
            if source_vtt_path.exists() and not lang_vtt_path.exists():
                shutil.copyfile(source_vtt_path, lang_vtt_path)
        if source_lang == "ko":
            targets = []
        elif source_lang == "zh":
            targets = ["en", "ko"]
        else:
            targets = ["ko"]
        manual_langs = []
        downloaded_subs = [source_srt_path]

    if not downloaded_subs:
        raise RuntimeError("No subtitles available and Whisper did not produce output")

    if source_lang is None and not targets:
        return

    if source_lang is None and manual_langs:
        if "en" in manual_langs and "ko" in manual_langs:
            return
        if "en" in manual_langs:
            source_lang = "en"
        elif "ko" in manual_langs:
            source_lang = "ko"
        elif any(lang.startswith("zh") for lang in manual_langs):
            source_lang = "zh"

    source_srt_path = out_dir / f"{source_lang}.srt" if source_lang else None
    if source_srt_path and not source_srt_path.exists():
        raise RuntimeError(f"Source SRT not found: {source_srt_path}")

    for target in targets:
        output_srt = out_dir / f"{target}.srt"
        _run_translate(
            translate_script,
            source_srt_path,
            output_srt,
            meta_path,
            source_lang,
            target,
            args.extra_context,
            args.chunk_seconds,
            args.overlap_seconds,
            args.max_workers,
            args.chunk_model,
            args.chunk_reasoning,
            args.merge_model,
            args.merge_reasoning,
            args.merge_chunk_seconds,
            args.merge_overlap_seconds,
            args.merge_workers,
            args.merge_pass,
            args.max_chars,
            args.min_duration,
            args.dry_run,
        )


if __name__ == "__main__":
    main()
