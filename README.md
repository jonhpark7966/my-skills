# My Skills

Custom Claude Code skills collection.

## Skills

### codex-review-gate

Automated code/document review gate using Codex CLI.

- **Default Model**: gpt-5.2
- **Default Reasoning Effort**: xhigh

Use for reviewing code, meeting notes, documents, and any text-based content.

#### Usage

```bash
python codex-review-gate/scripts/codex_review.py \
  --context "Description of what was done" \
  --code "path/to/file_or_content" \
  --cd "/project/root"
```

#### Triggers

- "review my work"
- "check this code"
- "run review gate"
- "get codex review"
