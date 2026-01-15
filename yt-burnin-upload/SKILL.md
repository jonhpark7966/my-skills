---
name: yt-burnin-upload
description: Download best-quality YouTube video/audio, burn in Korean subtitles (single line), then upload via YouTube Data API with Korean-translated title/description and unlisted privacy. Use when a user wants a hard-subbed version uploaded to a YouTube archive account.
---

# yt-burnin-upload

## Overview

Create a high-quality hard-subbed video for an archive account with Korean-only subtitles (single line).

## Quick start

```bash
python3 scripts/yt_burnin_upload.py "<YOUTUBE_URL>" --ko-srt ko.srt
```

## Workflow

1. Download best-quality video/audio.
2. Validate subtitle inputs (single-line cues).
3. Burn subtitles with ffmpeg.
4. Translate metadata to Korean and upload via YouTube Data API (unlisted).

## Step 1: Download best-quality source

```bash
yt-dlp -f "bv*+ba/b" -o "source.%(ext)s" "<URL>"
```

## Step 2: Prepare subtitle files

Inputs:
- `ko.srt` / `ko.vtt` for Korean output.

Rules:
- One line per cue, no line breaks.
- Do not shorten or summarize; split long cues by time if needed.

English subtitles are intentionally not burned in.

## Step 3: Burn in subtitles

Use a single subtitle filter for Korean only.
See `references/burnin-style.md` for recommended styles.

Example (SRT):

```bash
ffmpeg -i source.mp4 \
  -vf "subtitles=ko.srt:force_style='FontName=Noto Sans,FontSize=15,Outline=2,Shadow=1,Alignment=2,MarginV=50'" \
  -c:a copy burnin.mp4
```

## Step 4: Upload via YouTube Data API (OAuth)

Translate title and description to Korean with Codex CLI, then upload as unlisted.
OAuth client secret path is TODO.

See `references/upload-metadata.md` for the translation prompt and upload rules.

## Expected outputs

- `source.<ext>` best-quality download
- `burnin.mp4` hard-subbed output ready for upload
