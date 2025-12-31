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
