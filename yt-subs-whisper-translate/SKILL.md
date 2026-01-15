---
name: yt-subs-whisper-translate
description: Fetch manual YouTube subtitles (no auto captions), fall back to local Whisper (turbo) when manual subs are missing, then translate to Korean/English with Codex CLI. Use when a user provides a YouTube link and needs high-quality subtitles, bilingual subtitle generation, or SRT/VTT outputs.
---

# yt-subs-whisper-translate

## Overview

Acquire manual subtitles or generate SRT with local Whisper (turbo), then translate with Codex CLI and emit SRT/VTT outputs. Manual subtitles are always preferred; auto captions are never used.

## Quick start

End-to-end (manual subs → Whisper fallback → translations):

```bash
python3 scripts/yt_subs_whisper_translate.py "<YOUTUBE_URL>"
```

Translate a local SRT with chunked Codex CLI:

```bash
python3 scripts/translate_srt_codex.py --input source.srt --output ko.srt --meta meta.json --source-lang en --target-lang ko --write-vtt
```

## Workflow Decision Tree

1. List manual subtitles (ignore auto captions).
2. Choose a source track:
   - Manual `en` only -> translate to `ko`.
   - Manual `ko` only -> keep `ko`, do not create `en`.
   - Manual `zh*` -> translate to both `en` and `ko`.
   - Manual `en` + `ko` -> use both as-is.
   - No manual subs (or only auto captions) -> run Whisper (turbo).
3. Normalize cues to single-line (no line breaks).
4. Translate in 3-minute chunks with 30-second overlap using Codex CLI.
5. Merge translated chunks and export both `.srt` and `.vtt`.

## Step 1: Fetch metadata and manual subtitle inventory

Use metadata as translation context.

Example commands:

```bash
yt-dlp --dump-json --skip-download "<URL>" > meta.json
yt-dlp --list-subs "<URL>"
```

Only use the "Available subtitles" section. Ignore "Available automatic captions".

## Step 2: Acquire source subtitles

Manual subtitles:

```bash
yt-dlp --skip-download --write-subs --sub-lang "en,ko,zh,zh-Hans,zh-Hant" --sub-format srt "<URL>"
```

Whisper (when no manual subs or only auto captions):

```bash
whisper "<AUDIO_FILE>" --model turbo --output_format srt --output_dir ./subs
```

If the source language is known (e.g., Chinese), pass `--language zh` to Whisper.
If a Whisper SRT already exists in the output folder (e.g., `source.srt`), skip Whisper and reuse it.

Language handling:
- Manual `en` -> translate to `ko`.
- Manual `ko` -> keep `ko`, do not create `en`.
- Manual `zh*` or Whisper `zh` -> translate to both `en` and `ko`.
- Manual `en` + `ko` -> use both as-is.

## Step 3: Normalize SRT (single-line cues)

Rules:

- Keep one line per cue, no line breaks inside a cue.
- Do not summarize or shorten text.
- If a cue is too long, split it into multiple cues by time (allocate time proportionally to text length).

See `references/subtitle-normalization.md` for concrete heuristics.

## Step 4: Translate with Codex CLI (parallel chunks)

Split the source SRT into ~180s chunks with 30s overlap for better context.
Use `meta.json` title/description as background context in every prompt.
Run chunk translation with `gpt-5.2` and reasoning effort `medium` (default), using high parallelism (default 20).

Codex invocation format:

```bash
codex exec --skip-git-repo-check "@file PROMPT"
```

Parallelize chunk translation (e.g., with `xargs -P`).
See `references/translation-chunking.md` and `references/translation-prompt-template.md`.

## Step 5: Merge/repair with high-quality pass and export VTT

Merge chunks in chronological order.
Use the overlap to reconcile duplicates; keep one version in the overlap region by comparing time ranges and text.
After merging, run a repair pass with `gpt-5.2` and reasoning effort `high` to fix missing lines and formatting issues.
Use `references/translation-merge-template.md` for the repair prompt.

Export `.vtt`:

```bash
ffmpeg -i output.srt output.vtt
```

## Expected outputs

- `en.srt` / `en.vtt` when English exists or is translated
- `ko.srt` / `ko.vtt` when Korean exists or is translated
