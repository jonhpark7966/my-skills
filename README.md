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
