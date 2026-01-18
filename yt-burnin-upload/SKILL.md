---
name: yt-burnin-upload
description: Download best-quality YouTube video/audio, burn in Korean subtitles with optional English subtitles above (dual-subtitle mode), then upload via YouTube Data API with Korean-translated title/description and unlisted privacy. Use when a user wants a hard-subbed version uploaded to a YouTube archive account.
---

# yt-burnin-upload

## Overview

Create a high-quality hard-subbed video for an archive account with Korean subtitles (bottom, orange) and optional English subtitles above (cyan).

## Prerequisites

This skill requires a Korean subtitle file (`ko.srt`). If you don't have one, use `yt-subs-whisper-translate` first:

```bash
python3 yt-subs-whisper-translate/scripts/yt_subs_whisper_translate.py "<YOUTUBE_URL>"
```

This will generate `ko.srt` in the output folder, which you can then use with this skill.

## Quick start

```bash
python3 scripts/yt_burnin_upload.py "<YOUTUBE_URL>" --ko-srt path/to/ko.srt --en-srt path/to/en.srt
```

Both `--ko-srt` and `--en-srt` are required by default for dual-subtitle burn-in.

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
- `ko.srt` / `ko.vtt` for Korean subtitles (required).
- `en.srt` / `en.vtt` for English subtitles (optional).

Rules:
- One line per cue, no line breaks.
- Do not shorten or summarize; split long cues by time if needed.

## Step 3: Burn in subtitles

The script automatically detects video resolution and scales font/margin accordingly:

| Resolution | FontSize | Korean MarginV | English MarginV |
|------------|----------|----------------|-----------------|
| 720p       | 8        | 13             | 25              |
| 1080p      | 12       | 20             | 38              |
| 1440p      | 16       | 27             | 51              |
| 4K         | 24       | 40             | 76              |

Color scheme:
- **Korean**: #fe721a (orange) - bottom
- **English**: #43d6a9 (cyan/teal) - above Korean

Example (1080p, dual subtitles):

```bash
ffmpeg -i source.mp4 \
  -vf "subtitles=ko.srt:force_style='FontName=Noto Sans CJK KR,FontSize=12,PrimaryColour=&H1A72FE,Outline=2,Shadow=1,Alignment=2,MarginV=20',subtitles=en.srt:force_style='FontName=Noto Sans,FontSize=12,PrimaryColour=&HA9D643,Outline=2,Shadow=1,Alignment=2,MarginV=38'" \
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
