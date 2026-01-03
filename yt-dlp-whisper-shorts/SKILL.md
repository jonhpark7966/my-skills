---
name: yt-dlp-whisper-shorts
description: Download YouTube audio with yt-dlp, transcribe with Whisper to create timestamped subtitles (SRT), then analyze the transcript to recommend 15–60s Shorts-ready highlight segments with timecodes, hook text, clear reasons, and editing/narration suggestions. Use when a user provides a YouTube link and asks for transcription/subtitles, highlight extraction, or Shorts clip recommendations.
---

# yt-dlp + Whisper → Shorts Highlights

Use `scripts/yt_to_shorts.py` to automate: (1) audio download, (2) Whisper transcription, (3) highlight picking from the SRT.

## Quick start

Run end-to-end (download → transcribe → suggest):

`python3 scripts/yt_to_shorts.py "<YOUTUBE_URL>" --language ko --min-sec 15 --max-sec 60 --count 3`

Use an existing subtitle file (skip download/transcribe):

`python3 scripts/yt_to_shorts.py "<YOUTUBE_URL>" --no-download --no-transcribe --srt-file "<PATH_TO.srt>"`

## Workflow (agent)

1. Confirm:
   - The YouTube URL
   - Target language (use `--language ko` for Korean, or omit to auto-detect)
   - Desired Shorts length (default 15–60s) and number of picks (default 3)
2. Run `scripts/yt_to_shorts.py` and read the generated `highlights.md`.
3. Sanity-check each pick in the SRT:
   - Start should hook within 1–2s; if it starts slow, shift the in-point earlier to a stronger line.
   - Avoid section transitions (“다음으로…”) mid-clip; trim before the transition or add a 1-line narration bridge.
4. Respond with 3 candidates:
   - Exact start/end timecodes, duration
   - Clear selection reasons (hook, payoff, usefulness, emotion, proof shot)
   - Concrete edit plan (opening text, jump cuts, overlays/B-roll, optional narration)

## Outputs

Default output structure:

- `./yt_shorts/<video_id>/<video_id>.mp3` (when downloaded)
- `./yt_shorts/<video_id>/<video_id>.srt` (when transcribed)
- `./yt_shorts/<video_id>/highlights.md`
- `./yt_shorts/<video_id>/highlights.json`

## Notes

- Requires `yt-dlp` and `whisper` in `PATH`.
- Downloading from YouTube requires network access; in restricted environments this may require user approval.
- If yt-dlp warns about missing JS runtime (EJS), add an appropriate runtime or pass extra args via `--yt-dlp-args`.
- For additional heuristics/templates, see `references/shorts-selection.md`.
