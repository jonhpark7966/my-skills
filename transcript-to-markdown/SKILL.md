---
name: transcript-to-markdown
description: Convert a Korean transcript (SRT/VTT/plain text) into a detailed Markdown document with a 3-line summary and chaptered notes with timestamps. Use when a user provides transcript text and wants a structured Markdown writeup with minimal content loss.
---

# transcript-to-markdown

## Overview

Use Codex CLI to turn transcripts into a detailed, structured Markdown document with minimal information loss. Output includes a 3-line summary, chaptered notes with timestamps, and quoted key statements.

## Prerequisites

This skill works best with transcripts from `yt-subs-whisper-translate`. If you have a YouTube URL, generate the transcript first:

```bash
python3 yt-subs-whisper-translate/scripts/yt_subs_whisper_translate.py "<URL>"
```

## Quick start

Basic usage:

```bash
python3 scripts/transcript_to_markdown.py --input transcript.srt --output notes.md --title "Video Title"
```

With description and chapters:

```bash
python3 scripts/transcript_to_markdown.py \
  --input transcript.srt \
  --output notes.md \
  --title "Video Title" \
  --description "Video description for context" \
  --chapters chapters.json
```

## Workflow

1. Ingest transcript (SRT/VTT/plain text).
2. Smart chunking:
   - If chapters file provided → chunk by chapters
   - If chapter > 20 min → sub-chunk with 3 min overlap
   - If no chapters and > 20 min → time-based chunking (10 min chunks, 3 min overlap)
3. Process each chunk with Codex CLI.
4. Merge chunks with full context (title + description).
5. Claude final review and approval.

## Chunking logic

| Condition | Strategy |
|-----------|----------|
| Has chapters, each < 20 min | Use chapter boundaries |
| Has chapters, some > 20 min | Sub-chunk long chapters with overlap |
| No chapters, total < 20 min | Process as single chunk |
| No chapters, total > 20 min | 10 min chunks with 3 min overlap |

## Input formats

### SRT/VTT
Standard subtitle format with timestamps.

### Plain text
Requires `[MM:SS]` prefix per line:
```
[00:15] First point here
[01:30] Second point here
```

### Chapters file
JSON format (yt-dlp compatible):
```json
[
  {"start_time": 0, "end_time": 300, "title": "Introduction"},
  {"start_time": 300, "end_time": 900, "title": "Main Topic"}
]
```

Or simple text format:
```
00:00 Introduction
05:00 Main Topic
15:00 Conclusion
```

## Output format

```markdown
# Video Title

1. First summary point
2. Second summary point
3. Third summary point

## Chapter 1: Topic Name (00:00-05:00)

- [00:15] Detailed note with timestamp
- [00:45] Another important point
  - Supporting detail
  - Additional context

> "[01:30] Important quote from the speaker" — Speaker Name

## Chapter 2: Next Topic (05:00-15:00)
...
```

## Key features

- **Timestamps on every bullet**: `[MM:SS]` format for easy video reference
- **Blockquotes for key statements**: Important quotes preserved with speaker attribution
- **Minimal information loss**: Detailed notes, not summaries
- **Same language output**: Matches transcript language (default: Korean)

## Step 6: Claude final review and approval

After the merge pass completes, Claude must review the final Markdown output.

Review process:

1. Read the complete Markdown file.
2. Check for:
   - Timestamp accuracy and consistency
   - Proper quote formatting for key statements
   - Chapter organization and flow
   - Missing or duplicated content from chunk overlaps
   - Natural language and readability
3. Make direct edits to fix any issues found.
4. Report a summary of changes made (if any) to the user.

## Expected outputs

- `notes.md` — Final structured Markdown document
- `chunks/` — Intermediate files (deleted unless `--keep-chunks`)
