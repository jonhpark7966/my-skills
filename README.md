# My Skills

Custom Claude Code skills collection.

## Skills

### codex-review-gate

Automated code/document review gate using Codex CLI.

- **Default Model**: Codex CLI default (configurable via `CODEX_MODEL` env)
- **Default Reasoning Effort**: high (configurable via `CODEX_REASONING_EFFORT` env)
- **Sandbox**: read-only (safe, no file modifications)

Use for reviewing code, meeting notes, documents, and any text-based content.

#### Usage

```bash
python codex-review-gate/scripts/codex_review.py \
  --context "Description of what was done" \
  --code "path/to/file_or_content" \
  --cd "/project/root"
```

#### Environment Variables

```bash
export CODEX_MODEL="gpt-5.2"           # Optional: specify model
export CODEX_REASONING_EFFORT="xhigh"  # Optional: none/low/medium/high/xhigh
```

#### Triggers

- "review my work"
- "check this code"
- "run review gate"
- "get codex review"

---

### meeting-log-whisper-summary

Automate JJ_Vault meeting log processing: organize files into date folders, run Whisper transcription, and draft AI summaries.

- **Inputs**: Notes markdown file + audio recording (m4a/wav)
- **Outputs**: `YYMMDD/` folder with audio, SRT transcript, and `ai_summary.md`
- **Whisper Model**: medium (default), language: ko

#### Usage

```bash
python meeting-log-whisper-summary/scripts/prepare_meeting_log.py \
  --notes /path/to/YYMMDD.md \
  --audio /path/to/recording.m4a \
  --model medium \
  --language ko
```

#### Options

- `--mode copy|move`: Copy or move audio file (default: copy)
- `--date YYMMDD`: Override date if not in filename
- `--force`: Overwrite existing files
- `--no-whisper`: Skip transcription, only organize files

#### Triggers

- Providing a meeting notes file and audio recording
- Asking to transcribe and summarize a meeting

---

### yt-dlp-whisper-shorts

Download YouTube audio with yt-dlp, transcribe with Whisper to create timestamped subtitles (SRT), then analyze the transcript to recommend 15–60s Shorts-ready highlight segments.

- **Requirements**: `yt-dlp`, `whisper` in PATH
- **Outputs**: Audio (mp3), SRT transcript, highlights.md/json

#### Usage

```bash
python yt-dlp-whisper-shorts/scripts/yt_to_shorts.py "<YOUTUBE_URL>" \
  --language ko \
  --min-sec 15 \
  --max-sec 60 \
  --count 3
```

#### Options

- `--language`: Whisper language code (e.g., ko for Korean)
- `--min-sec`, `--max-sec`: Segment length range (default: 15-60s)
- `--count`: Number of highlight picks (default: 3)
- `--no-download`: Skip yt-dlp download
- `--no-transcribe`: Skip Whisper transcription
- `--srt-file`: Use existing SRT file

#### Triggers

- Providing a YouTube URL and asking for Shorts highlights
- Asking to transcribe and analyze a video for clips

---

### notes-to-archive

Convert verbose transcript notes from `transcript-to-markdown` into curated web archive entries for sudoremove.com.

- **Input**: Video folder with `notes.md`, `upload_info.json`, `meta.json`
- **Output**: Curated archive markdown + GitHub PR
- **Features**: Content curation, tag generation, git operations

#### What it does

1. Reads verbose notes.md (from transcript-to-markdown)
2. **Curates content** - selects ~30-50% of important points (not verbatim copy)
3. **Generates meaningful tags** - based on content (e.g., "Physical AI", "Robotics")
4. Creates archive markdown with proper schema
5. Git branch, commit, push, and create PR

#### Usage

This skill is designed to be called by Claude CLI:

```bash
claude -p "Use the notes-to-archive skill to process video folder /path/to/video and add to web archive"
```

Or invoked automatically by `youtube-storage/scripts/process_video.py` (step 4).

#### Triggers

- Asking to add processed video to web archive
- Asking to create curated archive entry from notes
