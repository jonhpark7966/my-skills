---
name: yt-burnin-upload
description: Download best-quality YouTube video/audio, burn in Korean subtitles (single line), then upload via YouTube Data API with Korean-translated title/description and unlisted privacy. Use when a user wants a hard-subbed version uploaded to a YouTube archive account.
---

# yt-burnin-upload

## Overview

Create a high-quality hard-subbed video for an archive account with Korean-only subtitles (single line).

## Prerequisites

This skill requires a Korean subtitle file (`ko.srt`). If you don't have one, use `yt-subs-whisper-translate` first:

```bash
python3 yt-subs-whisper-translate/scripts/yt_subs_whisper_translate.py "<YOUTUBE_URL>"
```

This will generate `ko.srt` in the output folder, which you can then use with this skill.

## Quick start

```bash
python3 scripts/yt_burnin_upload.py "<YOUTUBE_URL>" --ko-srt path/to/ko.srt
```

## Workflow

1. Generate Korean subtitles using `yt-subs-whisper-translate` (if not already available).
2. Download best-quality video/audio.
3. Validate subtitle inputs (single-line cues).
4. Burn subtitles with ffmpeg (auto-scaled for resolution).
5. Translate metadata to Korean.
6. Upload via YouTube Data API (TODO).

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

The script automatically detects video resolution and scales font size accordingly:

| Resolution | FontSize | MarginV |
|------------|----------|---------|
| 720p       | 12       | 35      |
| 1080p      | 15       | 50      |
| 1440p      | 20       | 65      |
| 4K+        | 27       | 90      |

Example (1080p):

```bash
ffmpeg -i source.mp4 \
  -vf "subtitles=ko.srt:force_style='FontName=Noto Sans,FontSize=15,Outline=2,Shadow=1,Alignment=2,MarginV=50'" \
  -c:a copy burnin.mp4
```

See `references/burnin-style.md` for recommended styles.

### Troubleshooting burn-in errors

If ffmpeg fails, check:
- **Font not installed**: Install Noto Sans via `brew install font-noto-sans` (macOS)
- **Invalid SRT format**: Ensure single-line cues, no internal line breaks
- **Disk space**: Burn-in creates a new video file
- **Codec issues**: Some codecs may require re-encoding

## Step 4: Translate metadata

Translate title and description to Korean with Codex CLI.
See `references/upload-metadata.md` for the translation prompt.

## Step 5: Upload via YouTube Data API (TODO)

Upload as unlisted. OAuth client secret configuration is TODO.

See `references/upload-metadata.md` for upload rules.

## Expected outputs

- `source.<ext>` best-quality download
- `burnin.mp4` hard-subbed output ready for upload
- `metadata_ko.json` translated title and description
