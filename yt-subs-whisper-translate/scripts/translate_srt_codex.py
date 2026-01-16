#!/usr/bin/env python3

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path

from srt_utils import SrtEntry, chunk_entries, format_srt, normalize_entries, parse_srt, write_srt, write_vtt

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


def _load_meta(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _render_prompt(
    template: str,
    source_lang: str,
    target_lang: str,
    title: str,
    description: str,
    extra_context: str,
    chunk_srt: str,
) -> str:
    return (
        template.replace("<SOURCE_LANG>", source_lang)
        .replace("<TARGET_LANG>", target_lang)
        .replace("<TITLE>", title)
        .replace("<DESCRIPTION>", description)
        .replace("<EXTRA_CONTEXT>", extra_context)
        .replace("<CHUNK_SRT>", chunk_srt)
    )


def _render_merge_prompt(
    template: str,
    source_lang: str,
    target_lang: str,
    title: str,
    description: str,
    extra_context: str,
    source_srt: str,
    candidate_srt: str,
) -> str:
    return (
        template.replace("<SOURCE_LANG>", source_lang)
        .replace("<TARGET_LANG>", target_lang)
        .replace("<TITLE>", title)
        .replace("<DESCRIPTION>", description)
        .replace("<EXTRA_CONTEXT>", extra_context)
        .replace("<CHUNK_SRT>", source_srt)
        .replace("<CANDIDATE_SRT>", candidate_srt)
    )


def _run_codex(
    prompt_path: Path,
    output_path: Path,
    model: str | None,
    reasoning_effort: str | None,
) -> None:
    _require_exe("codex")
    # Prefer writing the assistant's last message directly, otherwise stdout will
    # include execution logs, prompt echoes, and tool traces that break SRT parsing.
    cmd = ["codex", "exec", "--skip-git-repo-check", "--color", "never", "-o", str(output_path)]
    if model:
        cmd.extend(["--model", model])
    if reasoning_effort:
        cmd.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])
    cmd.append(f"@file {prompt_path}")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Codex CLI failed for {prompt_path}:\n{proc.stdout}")
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(
            f"Codex CLI succeeded but did not write output to {output_path} for {prompt_path}:\n{proc.stdout}"
        )


_TOKENS_USED_RE = re.compile(r"\s+tokens used\b.*$", re.IGNORECASE)


def _sanitize_cue_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = _TOKENS_USED_RE.sub("", text).strip()
    return text


def _dedupe_entries_keep_last(entries: list[SrtEntry]) -> list[SrtEntry]:
    # When `codex exec` output is accidentally captured from stdout, timestamps can
    # appear multiple times (prompt echo + final output). Keeping the last entry by
    # timestamp pair tends to preserve the actual answer.
    by_ts_ms: dict[tuple[int, int], str] = {}
    for entry in entries:
        key = (int(round(entry.start_s * 1000.0)), int(round(entry.end_s * 1000.0)))
        by_ts_ms[key] = _sanitize_cue_text(entry.text)
    deduped = [
        SrtEntry(start_s=start_ms / 1000.0, end_s=end_ms / 1000.0, text=text)
        for (start_ms, end_ms), text in sorted(by_ts_ms.items(), key=lambda kv: kv[0])
        if text
    ]
    return deduped


def _merge_chunks(chunks: list[tuple[float, float, list[SrtEntry]]], overlap: float) -> list[SrtEntry]:
    merged: list[SrtEntry] = []
    for idx, (chunk_start, _chunk_end, entries) in enumerate(chunks):
        if idx == 0:
            merged = list(entries)
            continue
        overlap_start = chunk_start
        overlap_end = chunk_start + overlap
        filtered: list[SrtEntry] = []
        for entry in merged:
            if entry.end_s <= overlap_start or entry.start_s >= overlap_end:
                filtered.append(entry)
        merged = filtered + list(entries)

    merged_sorted = sorted(merged, key=lambda e: (e.start_s, e.end_s))
    return merged_sorted


def _filter_entries(entries: list[SrtEntry], start_s: float, end_s: float) -> list[SrtEntry]:
    return [entry for entry in entries if entry.end_s > start_s and entry.start_s < end_s]


def _overlap_ratio(a: tuple[float, float], b: tuple[float, float]) -> float:
    a0, a1 = a
    b0, b1 = b
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    if union <= 0:
        return 0.0
    return inter / union


def _align_entries_to_source(source: list[SrtEntry], translated: list[SrtEntry]) -> list[SrtEntry]:
    if not source:
        return []
    if len(translated) == len(source):
        return [
            SrtEntry(start_s=src.start_s, end_s=src.end_s, text=tr.text)
            for src, tr in zip(source, translated)
        ]

    aligned: list[SrtEntry] = []
    for src in source:
        best_text = src.text
        best_overlap = 0.0
        for tr in translated:
            overlap = _overlap_ratio((src.start_s, src.end_s), (tr.start_s, tr.end_s))
            if overlap > best_overlap and tr.text.strip():
                best_overlap = overlap
                best_text = tr.text
        aligned.append(SrtEntry(start_s=src.start_s, end_s=src.end_s, text=best_text))
    return aligned


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate SRT with Codex CLI in parallel chunks.")
    parser.add_argument("--input", required=True, type=Path, help="Input SRT file")
    parser.add_argument("--output", required=True, type=Path, help="Output SRT file")
    parser.add_argument("--meta", required=True, type=Path, help="Metadata JSON (yt-dlp --dump-json)")
    parser.add_argument("--source-lang", required=True, help="Source language tag")
    parser.add_argument("--target-lang", required=True, help="Target language tag")
    parser.add_argument(
        "--template",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "references" / "translation-prompt-template.md",
        help="Prompt template path",
    )
    parser.add_argument("--extra-context", type=Path, help="Optional extra context text file")
    parser.add_argument("--chunk-seconds", type=float, default=180.0, help="Chunk size in seconds")
    parser.add_argument("--overlap-seconds", type=float, default=30.0, help="Chunk overlap in seconds")
    parser.add_argument("--max-workers", type=int, default=20, help="Parallel workers")
    parser.add_argument("--chunk-model", default="gpt-5.2", help="Codex model for chunk translation")
    parser.add_argument("--merge-model", default="gpt-5.2", help="Codex model for merge/repair")
    parser.add_argument("--chunk-reasoning", default="medium", help="Reasoning effort for chunk translation")
    parser.add_argument("--merge-reasoning", default="high", help="Reasoning effort for merge/repair")
    parser.add_argument(
        "--merge-template",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "references" / "translation-merge-template.md",
        help="Prompt template for merge/repair",
    )
    parser.add_argument("--merge-chunk-seconds", type=float, default=300.0, help="Merge chunk size in seconds")
    parser.add_argument("--merge-overlap-seconds", type=float, default=60.0, help="Merge overlap in seconds")
    parser.add_argument("--merge-workers", type=int, default=20, help="Parallel workers for merge/repair")
    parser.add_argument("--merge-pass", dest="merge_pass", action="store_true", default=True, help="Enable merge/repair")
    parser.add_argument("--no-merge-pass", dest="merge_pass", action="store_false", help="Disable merge/repair")
    parser.add_argument(
        "--merge-prompts-only",
        action="store_true",
        help="Write merge_prompt_*.txt but skip running the merge/repair Codex calls (writes initial merged output).",
    )
    parser.add_argument("--max-chars", type=int, default=42, help="Max characters per cue")
    parser.add_argument("--min-duration", type=float, default=0.8, help="Minimum cue duration (seconds)")
    parser.add_argument("--write-vtt", action="store_true", help="Also write VTT")
    parser.add_argument("--dry-run", action="store_true", help="Skip Codex call and echo input")
    parser.add_argument("--keep-chunks", action="store_true", help="Keep chunk temp files")
    args = parser.parse_args()

    if args.merge_prompts_only and not args.merge_pass:
        raise SystemExit("--merge-prompts-only requires merge pass to be enabled (omit --no-merge-pass).")

    template = args.template.read_text(encoding="utf-8")
    meta = _load_meta(args.meta)
    title = meta.get("title", "") or ""
    description = meta.get("description", "") or ""
    extra_context = ""
    if args.extra_context:
        extra_context = args.extra_context.read_text(encoding="utf-8", errors="replace").strip()

    entries = parse_srt(args.input)
    entries = normalize_entries(entries, max_chars=args.max_chars, min_duration_s=args.min_duration)
    chunks = chunk_entries(entries, args.chunk_seconds, args.overlap_seconds)
    if not chunks:
        raise RuntimeError("No subtitle entries to translate")

    total_duration = max(e.end_s for e in entries) if entries else 0.0
    logger.info(f"Input: {len(entries)} entries, {total_duration/60:.1f} min total duration")
    logger.info(f"Chunking: {len(chunks)} chunks ({args.chunk_seconds}s each, {args.overlap_seconds}s overlap)")
    logger.info(f"Chunk model: {args.chunk_model}, reasoning: {args.chunk_reasoning}")
    if args.merge_pass:
        logger.info(f"Merge model: {args.merge_model}, reasoning: {args.merge_reasoning}")

    out_dir = args.output.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir = out_dir / f"chunks_{args.target_lang}"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    chunk_specs: list[tuple[float, float, Path]] = []
    prompt_paths: list[Path] = []
    output_paths: list[Path] = []

    for idx, chunk in enumerate(chunks, start=1):
        chunk_srt_path = chunks_dir / f"chunk_{idx:03d}.srt"
        write_srt(chunk.entries, chunk_srt_path)
        chunk_specs.append((chunk.start_s, chunk.end_s, chunk_srt_path))
        logger.debug(f"Chunk {idx}/{len(chunks)}: {chunk.start_s/60:.1f}-{chunk.end_s/60:.1f} min, {len(chunk.entries)} entries")

        prompt_text = _render_prompt(
            template=template,
            source_lang=args.source_lang,
            target_lang=args.target_lang,
            title=title,
            description=description,
            extra_context=extra_context,
            chunk_srt=chunk_srt_path.read_text(encoding="utf-8"),
        )
        prompt_path = chunks_dir / f"prompt_{idx:03d}.txt"
        prompt_path.write_text(prompt_text, encoding="utf-8")
        prompt_paths.append(prompt_path)

        output_path = chunks_dir / f"translated_{idx:03d}.srt"
        output_paths.append(output_path)

    if args.dry_run:
        logger.info("Dry run: copying source chunks as output")
        for chunk_path, output_path in zip([c[2] for c in chunk_specs], output_paths):
            output_path.write_text(chunk_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        # Count how many chunks need translation (skip already completed)
        chunks_to_translate = sum(
            1 for output_path in output_paths
            if not (output_path.exists() and output_path.stat().st_size > 0)
        )
        if chunks_to_translate < len(output_paths):
            logger.info(f"Skipping {len(output_paths) - chunks_to_translate} already translated chunks")
        logger.info(f"Translating {chunks_to_translate} chunks with {args.max_workers} workers...")

        translation_start = time.time()
        completed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = []
            for prompt_path, output_path in zip(prompt_paths, output_paths):
                if output_path.exists() and output_path.stat().st_size > 0:
                    continue
                futures.append(executor.submit(_run_codex, prompt_path, output_path, args.chunk_model, args.chunk_reasoning))
            for fut in concurrent.futures.as_completed(futures):
                fut.result()
                completed += 1
                if completed % 5 == 0 or completed == chunks_to_translate:
                    logger.info(f"Translation progress: {completed}/{chunks_to_translate} chunks")
        translation_elapsed = time.time() - translation_start
        logger.info(f"Translation completed in {translation_elapsed:.1f}s ({translation_elapsed/60:.1f} min)")

    translated_chunks: list[tuple[float, float, list[SrtEntry]]] = []
    for (chunk_start, chunk_end, _chunk_path), output_path in zip(chunk_specs, output_paths):
        translated_entries = parse_srt(output_path)
        translated_entries = _filter_entries(translated_entries, chunk_start, chunk_end)
        translated_entries = _dedupe_entries_keep_last(translated_entries)
        translated_chunks.append((chunk_start, chunk_end, translated_entries))

    initial_merged = _merge_chunks(translated_chunks, args.overlap_seconds)

    merged = initial_merged
    merge_prompt_paths: list[Path] = []
    merge_output_paths: list[Path] = []

    if args.merge_pass:
        logger.info("Starting merge/repair pass...")
        merge_template = args.merge_template.read_text(encoding="utf-8")
        merge_dir = out_dir / f"merge_{args.target_lang}"
        merge_dir.mkdir(parents=True, exist_ok=True)

        merge_chunks = chunk_entries(entries, args.merge_chunk_seconds, args.merge_overlap_seconds)
        logger.info(f"Merge chunking: {len(merge_chunks)} chunks ({args.merge_chunk_seconds}s each, {args.merge_overlap_seconds}s overlap)")
        merge_specs: list[tuple[float, float, list[SrtEntry], list[SrtEntry], Path]] = []

        for idx, chunk in enumerate(merge_chunks, start=1):
            source_entries = chunk.entries
            candidate_entries = _filter_entries(initial_merged, chunk.start_s, chunk.end_s)
            source_srt = format_srt(source_entries)
            candidate_srt = format_srt(candidate_entries) if candidate_entries else ""
            prompt_text = _render_merge_prompt(
                template=merge_template,
                source_lang=args.source_lang,
                target_lang=args.target_lang,
                title=title,
                description=description,
                extra_context=extra_context,
                source_srt=source_srt,
                candidate_srt=candidate_srt,
            )
            prompt_path = merge_dir / f"merge_prompt_{idx:03d}.txt"
            prompt_path.write_text(prompt_text, encoding="utf-8")
            merge_prompt_paths.append(prompt_path)

            output_path = merge_dir / f"merge_{idx:03d}.srt"
            merge_output_paths.append(output_path)
            merge_specs.append((chunk.start_s, chunk.end_s, source_entries, candidate_entries, output_path))

        if not args.merge_prompts_only:
            if args.dry_run:
                logger.info("Dry run: using candidate/source as merge output")
                for _start, _end, source_entries, candidate_entries, output_path in merge_specs:
                    fallback = candidate_entries or source_entries
                    write_srt(fallback, output_path)
            else:
                # Count how many merge chunks need processing
                merge_chunks_to_process = sum(
                    1 for output_path in merge_output_paths
                    if not (output_path.exists() and output_path.stat().st_size > 0)
                )
                if merge_chunks_to_process < len(merge_output_paths):
                    logger.info(f"Skipping {len(merge_output_paths) - merge_chunks_to_process} already merged chunks")
                logger.info(f"Processing {merge_chunks_to_process} merge chunks with {args.merge_workers} workers...")

                merge_start = time.time()
                merge_completed = 0
                with concurrent.futures.ThreadPoolExecutor(max_workers=args.merge_workers) as executor:
                    futures = []
                    for prompt_path, output_path in zip(merge_prompt_paths, merge_output_paths):
                        if output_path.exists() and output_path.stat().st_size > 0:
                            continue
                        futures.append(
                            executor.submit(_run_codex, prompt_path, output_path, args.merge_model, args.merge_reasoning)
                        )
                    for fut in concurrent.futures.as_completed(futures):
                        fut.result()
                        merge_completed += 1
                        logger.info(f"Merge progress: {merge_completed}/{merge_chunks_to_process} chunks")
                merge_elapsed = time.time() - merge_start
                logger.info(f"Merge pass completed in {merge_elapsed:.1f}s ({merge_elapsed/60:.1f} min)")

        if not args.merge_prompts_only:
            repaired_chunks: list[tuple[float, float, list[SrtEntry]]] = []
            for start_s, end_s, source_entries, candidate_entries, output_path in merge_specs:
                translated_entries = parse_srt(output_path)
                translated_entries = _filter_entries(translated_entries, start_s, end_s)
                translated_entries = _dedupe_entries_keep_last(translated_entries)
                if not translated_entries:
                    translated_entries = candidate_entries
                aligned = _align_entries_to_source(source_entries, translated_entries)
                aligned = normalize_entries(aligned, max_chars=args.max_chars, min_duration_s=args.min_duration)
                repaired_chunks.append((start_s, end_s, aligned))

            merged = _merge_chunks(repaired_chunks, args.merge_overlap_seconds)

    write_srt(merged, args.output)
    logger.info(f"Output written: {args.output} ({len(merged)} entries)")
    if args.write_vtt:
        vtt_path = args.output.with_suffix(".vtt")
        write_vtt(merged, vtt_path)
        logger.info(f"VTT written: {vtt_path}")

    keep_artifacts = args.keep_chunks or args.merge_prompts_only
    if not keep_artifacts:
        for path in prompt_paths + output_paths + [c[2] for c in chunk_specs]:
            path.unlink(missing_ok=True)
        if chunks_dir.exists() and not any(chunks_dir.iterdir()):
            chunks_dir.rmdir()
        for path in merge_prompt_paths + merge_output_paths:
            path.unlink(missing_ok=True)
        merge_dir = out_dir / f"merge_{args.target_lang}"
        if merge_dir.exists() and not any(merge_dir.iterdir()):
            merge_dir.rmdir()


if __name__ == "__main__":
    main()
