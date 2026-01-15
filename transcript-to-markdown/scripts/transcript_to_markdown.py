#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Cue:
    start_s: float
    end_s: float
    text: str


@dataclass(frozen=True)
class Chapter:
    start_s: float
    end_s: float
    title: str


@dataclass(frozen=True)
class Chunk:
    start_s: float
    end_s: float
    cues: list[Cue]
    chapter_title: str | None = None


SRT_TS_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)

CHUNK_DURATION_THRESHOLD_S = 20 * 60  # 20 minutes
CHUNK_TARGET_S = 10 * 60  # 10 minutes per chunk
CHUNK_OVERLAP_S = 3 * 60  # 3 minutes overlap


def _parse_timestamp_s(ts: str) -> float:
    ts = ts.replace(",", ".")
    hh, mm, rest = ts.split(":")
    ss, ms = rest.split(".")
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0


def _format_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000.0))
    s_total, ms = divmod(total_ms, 1000)
    hh, rem = divmod(s_total, 3600)
    mm, ss = divmod(rem, 60)
    if hh > 0:
        return f"{hh:02d}:{mm:02d}:{ss:02d}"
    return f"{mm:02d}:{ss:02d}"


def _parse_srt_vtt(path: Path) -> list[Cue]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    cues: list[Cue] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.upper() == "WEBVTT":
            i += 1
            continue
        if line.isdigit():
            i += 1
            if i >= len(lines):
                break
            line = lines[i].strip()
        match = SRT_TS_RE.match(line)
        if not match:
            i += 1
            continue
        start_s = _parse_timestamp_s(match.group("start"))
        end_s = _parse_timestamp_s(match.group("end"))
        i += 1
        text_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i].strip())
            i += 1
        text = " ".join(text_lines).strip()
        if text:
            cues.append(Cue(start_s=start_s, end_s=end_s, text=text))
        i += 1
    return cues


def _parse_text(path: Path) -> list[Cue]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    cues: list[Cue] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(?:\[)?(?P<ts>\d{1,2}:\d{2})(?:\])?\s+(?P<text>.+)$", line)
        if not m:
            continue
        ts = m.group("ts")
        text = m.group("text")
        mm, ss = ts.split(":")
        start_s = int(mm) * 60 + int(ss)
        end_s = start_s + 3
        cues.append(Cue(start_s=start_s, end_s=end_s, text=text))
    return cues


def _parse_chapters(path: Path) -> list[Chapter]:
    """Parse chapters from JSON file (yt-dlp format) or simple text."""
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(text)
        if isinstance(data, list):
            chapters = []
            for item in data:
                start = item.get("start_time", 0)
                end = item.get("end_time", start + 600)
                title = item.get("title", "Untitled")
                chapters.append(Chapter(start_s=start, end_s=end, title=title))
            return chapters
        if isinstance(data, dict) and "chapters" in data:
            chapters = []
            for item in data["chapters"]:
                start = item.get("start_time", 0)
                end = item.get("end_time", start + 600)
                title = item.get("title", "Untitled")
                chapters.append(Chapter(start_s=start, end_s=end, title=title))
            return chapters
    except json.JSONDecodeError:
        pass
    # Try simple text format: "MM:SS Title" or "HH:MM:SS Title"
    chapters = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(?P<ts>[\d:]+)\s+(?P<title>.+)$", line)
        if m:
            ts_parts = m.group("ts").split(":")
            if len(ts_parts) == 2:
                start_s = int(ts_parts[0]) * 60 + int(ts_parts[1])
            else:
                start_s = int(ts_parts[0]) * 3600 + int(ts_parts[1]) * 60 + int(ts_parts[2])
            chapters.append(Chapter(start_s=start_s, end_s=start_s, title=m.group("title")))
    # Fix end times
    for i in range(len(chapters) - 1):
        chapters[i] = Chapter(start_s=chapters[i].start_s, end_s=chapters[i + 1].start_s, title=chapters[i].title)
    return chapters


def _filter_cues(cues: list[Cue], start_s: float, end_s: float) -> list[Cue]:
    return [c for c in cues if c.end_s > start_s and c.start_s < end_s]


def _chunk_by_chapters(cues: list[Cue], chapters: list[Chapter]) -> list[Chunk]:
    """Split cues by chapter boundaries."""
    chunks = []
    for ch in chapters:
        ch_cues = _filter_cues(cues, ch.start_s, ch.end_s)
        if ch_cues:
            chunks.append(Chunk(start_s=ch.start_s, end_s=ch.end_s, cues=ch_cues, chapter_title=ch.title))
    return chunks


def _chunk_by_time(cues: list[Cue], target_s: float, overlap_s: float) -> list[Chunk]:
    """Split cues into time-based chunks with overlap."""
    if not cues:
        return []
    total_duration = cues[-1].end_s - cues[0].start_s
    if total_duration <= CHUNK_DURATION_THRESHOLD_S:
        return [Chunk(start_s=cues[0].start_s, end_s=cues[-1].end_s, cues=cues)]

    chunks = []
    current_start = cues[0].start_s
    end_time = cues[-1].end_s

    while current_start < end_time:
        chunk_end = current_start + target_s
        chunk_cues = _filter_cues(cues, current_start, chunk_end)
        if chunk_cues:
            actual_end = min(chunk_end, chunk_cues[-1].end_s)
            chunks.append(Chunk(start_s=current_start, end_s=actual_end, cues=chunk_cues))
        current_start = chunk_end - overlap_s
        if current_start >= end_time:
            break

    return chunks


def _smart_chunk(cues: list[Cue], chapters: list[Chapter] | None) -> list[Chunk]:
    """Smart chunking: use chapters if available, fall back to time-based."""
    if chapters:
        chunks = _chunk_by_chapters(cues, chapters)
        # If any chapter is too long, sub-chunk it
        final_chunks = []
        for chunk in chunks:
            duration = chunk.end_s - chunk.start_s
            if duration > CHUNK_DURATION_THRESHOLD_S:
                sub_chunks = _chunk_by_time(chunk.cues, CHUNK_TARGET_S, CHUNK_OVERLAP_S)
                for i, sc in enumerate(sub_chunks):
                    title = f"{chunk.chapter_title} (Part {i + 1})" if chunk.chapter_title else None
                    final_chunks.append(Chunk(start_s=sc.start_s, end_s=sc.end_s, cues=sc.cues, chapter_title=title))
            else:
                final_chunks.append(chunk)
        return final_chunks
    return _chunk_by_time(cues, CHUNK_TARGET_S, CHUNK_OVERLAP_S)


def _format_cues(cues: list[Cue]) -> str:
    lines: list[str] = []
    for cue in cues:
        text = re.sub(r"\s+", " ", cue.text).strip()
        if not text:
            continue
        ts = _format_timestamp(cue.start_s)
        lines.append(f"[{ts}] {text}")
    return "\n".join(lines)


def _require_exe(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required executable not found in PATH: {name}")
    return path


def _render_chunk_prompt(template: str, title: str, description: str, transcript: str, language: str, chapter_title: str | None) -> str:
    chapter_context = f"\nCurrent chapter: {chapter_title}" if chapter_title else ""
    return (
        template.replace("<TITLE>", title)
        .replace("<DESCRIPTION>", description)
        .replace("<LANGUAGE>", language)
        .replace("<CHAPTER_CONTEXT>", chapter_context)
        .replace("<TRANSCRIPT>", transcript)
    )


def _render_merge_prompt(template: str, title: str, description: str, chunk_outputs: str, language: str) -> str:
    return (
        template.replace("<TITLE>", title)
        .replace("<DESCRIPTION>", description)
        .replace("<LANGUAGE>", language)
        .replace("<CHUNK_OUTPUTS>", chunk_outputs)
    )


def _run_codex(prompt_path: Path, output_path: Path, model: str, reasoning: str) -> None:
    _require_exe("codex")
    cmd = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--model",
        model,
        "-c",
        f'model_reasoning_effort="{reasoning}"',
        "-o",
        str(output_path),
        f"@file {prompt_path}",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Codex CLI failed:\n{proc.stdout}")
    if not output_path.exists() or not output_path.read_text(encoding="utf-8").strip():
        raise RuntimeError("Codex output was empty")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert transcript to Markdown with chapters.")
    parser.add_argument("--input", required=True, type=Path, help="Input transcript (SRT/VTT/TXT)")
    parser.add_argument("--output", required=True, type=Path, help="Output Markdown path")
    parser.add_argument("--title", default="Untitled", help="Document title")
    parser.add_argument("--description", default="", help="Video description for context")
    parser.add_argument("--chapters", type=Path, help="Chapters file (JSON or text format)")
    parser.add_argument("--language", default="Korean", help="Transcript language label")
    parser.add_argument(
        "--template",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "references" / "codex-chunk-template.md",
        help="Chunk prompt template path",
    )
    parser.add_argument(
        "--merge-template",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "references" / "codex-merge-template.md",
        help="Merge prompt template path",
    )
    parser.add_argument("--model", default="gpt-5.2", help="Codex model")
    parser.add_argument("--chunk-reasoning", default="medium", help="Reasoning effort for chunks")
    parser.add_argument("--merge-reasoning", default="high", help="Reasoning effort for merge")
    parser.add_argument("--dry-run", action="store_true", help="Write prompts only; skip Codex calls")
    parser.add_argument("--keep-chunks", action="store_true", help="Keep intermediate chunk files")
    args = parser.parse_args()

    if not args.input.exists():
        raise RuntimeError(f"Input not found: {args.input}")

    suffix = args.input.suffix.lower()
    if suffix in {".srt", ".vtt"}:
        cues = _parse_srt_vtt(args.input)
    else:
        cues = _parse_text(args.input)

    if not cues:
        raise RuntimeError("No cues parsed. Provide SRT/VTT or timestamped text.")

    chapters = None
    if args.chapters and args.chapters.exists():
        chapters = _parse_chapters(args.chapters)

    chunks = _smart_chunk(cues, chapters)
    template = args.template.read_text(encoding="utf-8")

    out_dir = args.output.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir = out_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    chunk_outputs: list[str] = []

    for idx, chunk in enumerate(chunks, start=1):
        transcript = _format_cues(chunk.cues)
        prompt = _render_chunk_prompt(
            template, args.title, args.description, transcript, args.language, chunk.chapter_title
        )
        prompt_path = chunks_dir / f"chunk_{idx:03d}.prompt.txt"
        output_path = chunks_dir / f"chunk_{idx:03d}.md"
        prompt_path.write_text(prompt, encoding="utf-8")

        if not args.dry_run:
            if not output_path.exists() or not output_path.read_text(encoding="utf-8").strip():
                _run_codex(prompt_path, output_path, args.model, args.chunk_reasoning)
            chunk_outputs.append(output_path.read_text(encoding="utf-8"))

    if args.dry_run:
        return

    # If single chunk, use directly
    if len(chunk_outputs) == 1:
        args.output.write_text(chunk_outputs[0], encoding="utf-8")
    else:
        # Merge chunks
        merge_template = args.merge_template.read_text(encoding="utf-8")
        combined = "\n\n---\n\n".join(chunk_outputs)
        merge_prompt = _render_merge_prompt(merge_template, args.title, args.description, combined, args.language)
        merge_prompt_path = out_dir / "merge.prompt.txt"
        merge_prompt_path.write_text(merge_prompt, encoding="utf-8")
        _run_codex(merge_prompt_path, args.output, args.model, args.merge_reasoning)

    # Cleanup
    if not args.keep_chunks:
        for f in chunks_dir.iterdir():
            f.unlink()
        chunks_dir.rmdir()


if __name__ == "__main__":
    main()
