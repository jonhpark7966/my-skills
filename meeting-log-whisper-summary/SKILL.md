---
name: meeting-log-whisper-summary
description: Automate JJ_Vault meeting log processing when given a human-written meeting notes markdown file and an audio recording (m4a/wav). Use for creating date-based meeting_logs/DATE folders, running Whisper to generate DATE.srt, and drafting ai_summary.md that enriches the notes with transcript context.
---

# Meeting Log Whisper Summary

## Overview

Automate the JJ_Vault meeting log pipeline: infer the meeting date, organize files into a date folder, run Whisper to create the SRT transcript, then draft `ai_summary.md` by combining human notes with transcript details.

## Workflow

### 1) Gather inputs

- Notes markdown file, typically `JJ_Vault/meeting_logs/YYMMDD.md`.
- Audio recording file (e.g., `.m4a`).
- If filenames do not contain a date, request the date explicitly.

### 2) Prepare folder + transcription

Run the helper script to create the date folder, place the audio, and generate `YYMMDD.srt`.

Example:

```bash
python scripts/prepare_meeting_log.py \
  --notes /path/to/JJ_Vault/meeting_logs/YYMMDD.md \
  --audio /path/to/recording.m4a \
  --model medium \
  --language ko \
  --mode copy
```

- Use `--mode move` to move the original audio.
- Use `--date` if the date cannot be inferred.
- Use `--force` to overwrite existing audio/SRT.
- Use `--no-whisper` to only organize files.

Expected outputs under `JJ_Vault/meeting_logs/YYMMDD/`:
- `YYMMDD.<ext>` (audio)
- `YYMMDD.srt`

### 3) Draft ai_summary.md

- Read the notes first; treat them as ground truth.
- Scan the SRT to add missing context, decisions, metrics, or action items.
- Write `JJ_Vault/meeting_logs/YYMMDD/ai_summary.md` using `references/ai_summary_template.md`.
- Flag ambiguity or conflicts under "확인 필요".

### 4) Verify

Confirm the date folder includes the audio, SRT, and `ai_summary.md`.

## Resources

### scripts/prepare_meeting_log.py

Create the date folder, place the audio, and run Whisper.

### references/ai_summary_template.md

Summary template and guidance for `ai_summary.md`.
