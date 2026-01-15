#!/usr/bin/env python3

from __future__ import annotations

import dataclasses
import re
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class SrtEntry:
    start_s: float
    end_s: float
    text: str


@dataclasses.dataclass(frozen=True)
class SrtChunk:
    start_s: float
    end_s: float
    entries: list[SrtEntry]


SRT_TS_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)


def parse_timestamp_s(ts: str) -> float:
    ts = ts.replace(",", ".")
    hh, mm, rest = ts.split(":")
    ss, ms = rest.split(".")
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0


def format_timestamp_s(seconds: float, sep: str = ",") -> str:
    if seconds < 0:
        seconds = 0.0
    ms_total = int(round(seconds * 1000.0))
    s_total, ms = divmod(ms_total, 1000)
    hh, rem = divmod(s_total, 3600)
    mm, ss = divmod(rem, 60)
    return f"{hh:02d}:{mm:02d}:{ss:02d}{sep}{ms:03d}"


def parse_srt(path: Path) -> list[SrtEntry]:
    entries: list[SrtEntry] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if line.isdigit():
            i += 1
            if i >= len(lines):
                break
            line = lines[i].strip()

        m = SRT_TS_RE.match(line)
        if not m:
            i += 1
            continue

        start_s = parse_timestamp_s(m.group("start"))
        end_s = parse_timestamp_s(m.group("end"))
        i += 1

        text_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i].strip())
            i += 1

        text = " ".join(text_lines).strip()
        if text:
            entries.append(SrtEntry(start_s=start_s, end_s=end_s, text=text))
        i += 1

    return entries


def format_srt(entries: list[SrtEntry]) -> str:
    blocks: list[str] = []
    for idx, entry in enumerate(entries, start=1):
        start_ts = format_timestamp_s(entry.start_s, sep=",")
        end_ts = format_timestamp_s(entry.end_s, sep=",")
        blocks.append(f"{idx}\n{start_ts} --> {end_ts}\n{entry.text}\n")
    return "\n".join(blocks).strip() + "\n"


def write_srt(entries: list[SrtEntry], path: Path) -> None:
    path.write_text(format_srt(entries), encoding="utf-8")


def write_vtt(entries: list[SrtEntry], path: Path) -> None:
    blocks: list[str] = ["WEBVTT", ""]
    for entry in entries:
        start_ts = format_timestamp_s(entry.start_s, sep=".")
        end_ts = format_timestamp_s(entry.end_s, sep=".")
        blocks.append(f"{start_ts} --> {end_ts}\n{entry.text}\n")
    path.write_text("\n".join(blocks).strip() + "\n", encoding="utf-8")


def _split_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    if " " in text:
        words = text.split()
        parts: list[str] = []
        current: list[str] = []
        for word in words:
            if not current:
                current = [word]
                continue
            candidate = " ".join(current + [word])
            if len(candidate) <= max_chars:
                current.append(word)
            else:
                parts.append(" ".join(current))
                current = [word]
        if current:
            parts.append(" ".join(current))
    else:
        parts = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    normalized: list[str] = []
    for part in parts:
        if len(part) <= max_chars:
            normalized.append(part)
        else:
            normalized.extend([part[i : i + max_chars] for i in range(0, len(part), max_chars)])
    return normalized


def normalize_entries(
    entries: list[SrtEntry],
    max_chars: int,
    min_duration_s: float = 0.8,
) -> list[SrtEntry]:
    normalized: list[SrtEntry] = []
    for entry in entries:
        text = re.sub(r"\s+", " ", entry.text).strip()
        if not text:
            continue
        parts = _split_text(text, max_chars)
        if len(parts) == 1:
            normalized.append(SrtEntry(entry.start_s, entry.end_s, parts[0]))
            continue

        total_duration = max(entry.end_s - entry.start_s, min_duration_s * len(parts))
        total_len = sum(len(p) for p in parts)
        durations = [total_duration * (len(p) / total_len) for p in parts]

        if sum(max(d, min_duration_s) for d in durations) > total_duration:
            durations = [total_duration / len(parts)] * len(parts)
        else:
            durations = [max(d, min_duration_s) for d in durations]
            scale = total_duration / sum(durations)
            durations = [d * scale for d in durations]

        start = entry.start_s
        for idx, (part, dur) in enumerate(zip(parts, durations)):
            end = entry.end_s if idx == len(parts) - 1 else start + dur
            normalized.append(SrtEntry(start, end, part))
            start = end

    return normalized


def chunk_entries(
    entries: list[SrtEntry],
    chunk_seconds: float,
    overlap_seconds: float,
) -> list[SrtChunk]:
    if not entries:
        return []

    sorted_entries = sorted(entries, key=lambda e: (e.start_s, e.end_s))
    start = max(0.0, sorted_entries[0].start_s)
    end_limit = sorted_entries[-1].end_s
    chunks: list[SrtChunk] = []
    start_idx = 0

    while start < end_limit:
        end = start + chunk_seconds
        while start_idx < len(sorted_entries) and sorted_entries[start_idx].end_s < start:
            start_idx += 1
        chunk_items: list[SrtEntry] = []
        idx = start_idx
        while idx < len(sorted_entries) and sorted_entries[idx].start_s <= end:
            chunk_items.append(sorted_entries[idx])
            idx += 1
        if chunk_items:
            chunks.append(SrtChunk(start_s=start, end_s=end, entries=chunk_items))
        start = start + chunk_seconds - overlap_seconds

    return chunks
