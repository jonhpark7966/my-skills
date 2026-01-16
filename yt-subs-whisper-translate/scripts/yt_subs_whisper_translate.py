#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

from srt_utils import normalize_entries, parse_srt, write_srt, write_vtt

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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


def _download_audio(url: str, out_dir: Path, video_id: str) -> Path:
    """Download audio for Whisper processing."""
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
    logger.info("Downloading audio...")
    start = time.time()
    _run(cmd)
    elapsed = time.time() - start
    audio_path = out_dir / f"{video_id}.mp3"
    if not audio_path.exists():
        raise RuntimeError(f"Audio download finished but {audio_path} not found")
    logger.info(f"Audio downloaded in {elapsed:.1f}s: {audio_path}")
    return audio_path


def _detect_audio_language(audio_path: Path) -> str:
    """Detect audio language using Whisper.

    Runs Whisper without --language flag to trigger auto-detection.
    Whisper prints 'Detected language: X' to stderr.
    """
    _require_exe("whisper")
    logger.info("Detecting audio language with Whisper...")
    start = time.time()

    # Run whisper without --language to trigger auto-detection
    # Use tiny model for fast detection, output to temp dir
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "whisper",
            str(audio_path),
            "--model", "tiny",  # Fast model for detection
            "--output_format", "txt",
            "--output_dir", tmpdir,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 min timeout
            )
            elapsed = time.time() - start

            # Whisper prints "Detected language: English" to stderr
            output = proc.stderr + proc.stdout
            for line in output.splitlines():
                if "detected language" in line.lower():
                    # Extract language name after colon
                    lang = line.split(":")[-1].strip().lower()
                    # Remove any trailing info like probability
                    lang = lang.split()[0] if lang else "english"
                    lang_code = _language_to_code(lang)
                    logger.info(f"Detected audio language: {lang} ({lang_code}) in {elapsed:.1f}s")
                    return lang_code

            # If no explicit detection message, check if transcription succeeded
            if proc.returncode == 0:
                logger.warning("Language detection: no explicit language found, defaulting to 'en'")
                return "en"

        except subprocess.TimeoutExpired:
            logger.warning("Language detection timed out")
        except Exception as e:
            logger.warning(f"Language detection failed: {e}")

    logger.info("Fallback: defaulting to English")
    return "en"


def _language_to_code(lang_name: str) -> str:
    """Convert language name to code."""
    mapping = {
        "english": "en",
        "korean": "ko",
        "chinese": "zh",
        "mandarin": "zh",
        "japanese": "ja",
        "spanish": "es",
        "french": "fr",
        "german": "de",
    }
    return mapping.get(lang_name.lower(), "en")


def _select_manual_subs_for_audio_lang(subtitles: dict, audio_lang: str) -> tuple[str | None, list[str], list[str]]:
    """
    Select manual subtitles based on audio language.
    Priority: audio language matching subtitle > other manual subs > whisper fallback
    """
    langs = set(subtitles.keys())

    # Find subtitles matching audio language
    audio_lang_subs = sorted([lang for lang in langs if lang == audio_lang or lang.startswith(f"{audio_lang}-")])
    ko_langs = sorted([lang for lang in langs if lang == "ko" or lang.startswith("ko-")])

    if audio_lang == "en":
        if audio_lang_subs:
            # English audio + English subs available
            en_pref = "en" if "en" in audio_lang_subs else audio_lang_subs[0]
            if ko_langs:
                ko_pref = "ko" if "ko" in ko_langs else ko_langs[0]
                return None, [en_pref, ko_pref], []  # Both available, no translation needed
            return "en", [en_pref], ["ko"]  # Need to translate to Korean
        else:
            # English audio but no English subs -> use Whisper
            return None, [], []

    elif audio_lang == "zh":
        if audio_lang_subs:
            # Chinese audio + Chinese subs
            zh_pref = "zh-Hans" if "zh-Hans" in audio_lang_subs else "zh-Hant" if "zh-Hant" in audio_lang_subs else audio_lang_subs[0]
            return "zh", [zh_pref], ["en", "ko"]
        else:
            return None, [], []

    elif audio_lang == "ko":
        if ko_langs:
            ko_pref = "ko" if "ko" in ko_langs else ko_langs[0]
            return "ko", [ko_pref], []  # Korean audio + Korean subs, no translation
        else:
            return None, [], []

    else:
        # Other languages - check if matching subs exist
        if audio_lang_subs:
            return audio_lang, [audio_lang_subs[0]], ["en", "ko"]
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
    logger.info(f"Downloading manual subtitles: {langs}")
    start = time.time()
    _run(cmd)
    elapsed = time.time() - start

    downloaded: list[Path] = []
    for lang in langs:
        matches = sorted(out_dir.glob(f"{video_id}.{lang}*.srt"))
        if matches:
            downloaded.append(matches[0])
    logger.info(f"Downloaded {len(downloaded)} subtitle files in {elapsed:.1f}s")
    return downloaded


def _whisper_transcribe(
    audio_path: Path,
    out_dir: Path,
    model: str,
    language: str | None,
    word_timestamps: bool,
    max_words_per_line: int | None,
    max_line_count: int | None,
) -> Path:
    _require_exe("whisper")
    out_dir.mkdir(parents=True, exist_ok=True)
    srt_path = out_dir / f"{audio_path.stem}.srt"
    if srt_path.exists():
        logger.info(f"Using existing Whisper output: {srt_path}")
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
    if word_timestamps:
        cmd.extend(["--word_timestamps", "True"])
        if max_words_per_line:
            cmd.extend(["--max_words_per_line", str(max_words_per_line)])
        if max_line_count:
            cmd.extend(["--max_line_count", str(max_line_count)])

    logger.info(f"Running Whisper transcription (model={model}, language={language})...")
    start = time.time()
    _run(cmd)
    elapsed = time.time() - start

    if not srt_path.exists():
        raise RuntimeError(f"Whisper finished but SRT not found: {srt_path}")

    logger.info(f"Whisper transcription completed in {elapsed:.1f}s")
    return srt_path


def _detect_language_from_text(entries: list) -> str:
    """Detect language from subtitle text content."""
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
    logger.info(f"Translating {source_lang} -> {target_lang}")
    logger.info(f"  Chunk: {chunk_seconds}s, overlap: {overlap_seconds}s, workers: {max_workers}")
    logger.info(f"  Chunk model: {chunk_model}, reasoning: {chunk_reasoning}")
    logger.info(f"  Merge model: {merge_model}, reasoning: {merge_reasoning}")

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

    start = time.time()
    subprocess.run(cmd, check=True)
    elapsed = time.time() - start
    logger.info(f"Translation {source_lang} -> {target_lang} completed in {elapsed:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch manual subs, run Whisper fallback, translate with Codex.")
    parser.add_argument("url", nargs="?", help="YouTube URL")
    parser.add_argument("--out-dir", type=Path, help="Output directory")
    parser.add_argument("--meta", type=Path, help="Existing metadata JSON (skip yt-dlp)")
    parser.add_argument("--source-srt", type=Path, help="Use an existing source SRT (skip yt-dlp/whisper)")
    parser.add_argument("--source-lang", help="Override detected source language")
    parser.add_argument("--whisper-language", help="Whisper language hint")
    parser.add_argument("--model", default="turbo", help="Whisper model")
    parser.add_argument(
        "--whisper-word-timestamps",
        dest="whisper_word_timestamps",
        action="store_true",
        default=True,
        help="Enable Whisper word-level timestamps",
    )
    parser.add_argument(
        "--no-whisper-word-timestamps",
        dest="whisper_word_timestamps",
        action="store_false",
        help="Disable Whisper word-level timestamps",
    )
    parser.add_argument("--whisper-max-words", type=int, default=8, help="Max words per line (requires word timestamps)")
    parser.add_argument("--whisper-max-line-count", type=int, default=1, help="Max lines per segment")
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

    total_start = time.time()

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

        logger.info(f"Processing video: {video_id}")
        logger.info(f"Output directory: {out_dir}")

        meta = _yt_dlp_meta(args.url, meta_path)

    if meta_path and meta_path.exists() and not meta:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    translate_script = Path(__file__).resolve().parent / "translate_srt_codex.py"

    # Handle --source-srt case
    if args.source_srt:
        source_lang = args.source_lang or _detect_language_from_text(parse_srt(source_srt))
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

    # Step 1: Detect audio language
    logger.info("=" * 50)
    logger.info("Step 1: Detecting audio language...")
    audio_path = _download_audio(args.url, out_dir, video_id)

    if args.whisper_language:
        audio_lang = args.whisper_language
        logger.info(f"Using specified language: {audio_lang}")
    else:
        audio_lang = _detect_audio_language(audio_path)

    # Step 2: Check for matching manual subtitles
    logger.info("=" * 50)
    logger.info("Step 2: Checking manual subtitles...")
    subtitles = meta.get("subtitles", {})
    available_langs = list(subtitles.keys())
    logger.info(f"Audio language: {audio_lang}")
    logger.info(f"Available manual subtitles: {available_langs}")

    source_lang, manual_langs, targets = _select_manual_subs_for_audio_lang(subtitles, audio_lang)

    downloaded_subs: list[Path] = []
    use_whisper = False

    if manual_langs:
        logger.info(f"Using manual subtitles: {manual_langs}")
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
        logger.info(f"No matching manual subtitles for audio language '{audio_lang}'. Using Whisper.")
        use_whisper = True

    # Step 3: Whisper transcription if needed
    if use_whisper or not downloaded_subs:
        logger.info("=" * 50)
        logger.info("Step 3: Whisper transcription...")
        source_srt_path = out_dir / "source.srt"

        if not source_srt_path.exists():
            candidate_whisper = out_dir / f"{video_id}.srt"
            if candidate_whisper.exists():
                source_srt_path.write_text(candidate_whisper.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                whisper_srt = _whisper_transcribe(
                    audio_path,
                    out_dir,
                    args.model,
                    audio_lang,  # Use detected audio language
                    args.whisper_word_timestamps,
                    args.whisper_max_words,
                    args.whisper_max_line_count,
                )
                source_srt_path.write_text(whisper_srt.read_text(encoding="utf-8"), encoding="utf-8")

        _normalize_file(source_srt_path, args.max_chars, args.min_duration)
        source_lang = audio_lang

        # Copy to language-specific file
        lang_srt_path = out_dir / f"{source_lang}.srt"
        if not lang_srt_path.exists():
            shutil.copyfile(source_srt_path, lang_srt_path)
            source_vtt_path = source_srt_path.with_suffix(".vtt")
            lang_vtt_path = out_dir / f"{source_lang}.vtt"
            if source_vtt_path.exists() and not lang_vtt_path.exists():
                shutil.copyfile(source_vtt_path, lang_vtt_path)

        # Set translation targets
        if source_lang == "ko":
            targets = []
        elif source_lang == "zh":
            targets = ["en", "ko"]
        else:
            targets = ["ko"]

        downloaded_subs = [source_srt_path]

    if not downloaded_subs:
        raise RuntimeError("No subtitles available and Whisper did not produce output")

    # Step 4: Translation
    if targets:
        logger.info("=" * 50)
        logger.info(f"Step 4: Translation ({source_lang} -> {targets})...")

        source_srt_path = out_dir / f"{source_lang}.srt"
        if not source_srt_path.exists():
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
    else:
        logger.info("No translation needed.")

    total_elapsed = time.time() - total_start
    logger.info("=" * 50)
    logger.info(f"Total processing time: {total_elapsed:.1f}s")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
