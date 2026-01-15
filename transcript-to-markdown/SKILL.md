---
name: transcript-to-markdown
description: Convert a Korean transcript (SRT/VTT/plain text) into a detailed Markdown document with a 3-line summary and chaptered notes with timestamps. Use when a user provides transcript text and wants a structured Markdown writeup with minimal content loss.
---

# transcript-to-markdown

## Overview

Use Codex CLI to turn transcripts into a detailed, structured Markdown document with minimal information loss. Output includes only a 3-line summary and chaptered notes with timestamps.

## Quick start

```bash
python3 scripts/transcript_to_markdown.py --input transcript.srt --output notes.md --title "Video Title"
```

## Workflow

1. Ingest transcript (SRT/VTT/plain text).
2. Format transcript with timestamps.
3. Use Codex CLI to produce Markdown using the prompt template.

## Step 1: Ingest transcript

- For SRT/VTT: keep timestamps and text per cue.
- For plain text: requires `[MM:SS]` prefix per line.

## Step 2: Create chapters

Codex is responsible for chaptering based on the transcript content and timestamps.

## Step 3: Write Markdown

Rules:
- Top section is exactly 3 lines of summary.
- Chapters include timestamps and detailed notes.
- Do not omit important facts or steps; preserve technical detail.
- Use the same language as the transcript.

See `references/codex-summary-template.md`.
