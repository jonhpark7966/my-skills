#!/usr/bin/env python3

from __future__ import annotations

import argparse
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


SRT_TS_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)


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


def _render_prompt(template: str, title: str, transcript: str, language: str) -> str:
    return (
        template.replace("<TITLE>", title)
        .replace("<LANGUAGE>", language)
        .replace("<TRANSCRIPT>", transcript)
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
    parser.add_argument("--language", default="Korean", help="Transcript language label")
    parser.add_argument(
        "--template",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "references" / "codex-summary-template.md",
        help="Prompt template path",
    )
    parser.add_argument("--model", default="gpt-5.2", help="Codex model")
    parser.add_argument("--reasoning", default="high", help="Reasoning effort")
    parser.add_argument("--dry-run", action="store_true", help="Write prompt only; skip Codex call")
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
    transcript = _format_cues(cues)
    template = args.template.read_text(encoding="utf-8")
    prompt = _render_prompt(template, args.title, transcript, args.language)
    prompt_path = args.output.with_suffix(".prompt.txt")
    prompt_path.write_text(prompt, encoding="utf-8")

    if args.dry_run:
        return

    _run_codex(prompt_path, args.output, args.model, args.reasoning)


if __name__ == "__main__":
    main()
