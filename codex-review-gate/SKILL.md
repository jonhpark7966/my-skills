---
name: codex-review-gate
description: Automated code review gate using Codex CLI. Use when completing a task and needing external AI review before proceeding. Requests structured review from Codex, determines pass/fail verdict, auto-retries on failure with improvements, and reports to user if gate fails twice. Triggers on phrases like "review my work", "check this code", "run review gate", "get codex review", or when a significant implementation task is completed.
---

# Codex Review Gate

Request structured code review from Codex CLI, evaluate pass/fail verdict, and manage the review-improve-retry workflow automatically.

## Prerequisites

- Codex CLI installed and in PATH
- Valid credentials at `~/.codex/config.toml`
- Verify: `codex --version`

## Review Gate Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                       REVIEW GATE                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. PREPARE CONTEXT                                         │
│     └─ Summarize: what was done, what changed, why          │
│                                                             │
│  2. REQUEST REVIEW (scripts/codex_review.py)                │
│     └─ sandbox: read-only (safe, no file modifications)     │
│     └─ reasoning: high (default, configurable via env)      │
│                                                             │
│  3. EVALUATE VERDICT                                        │
│     ├─ PASS → Proceed to next task                          │
│     └─ FAIL → Go to step 4                                  │
│                                                             │
│  4. IMPROVE (Claude fixes based on review feedback)         │
│     └─ Address issues raised in review                      │
│                                                             │
│  5. RETRY REVIEW (2nd attempt)                              │
│     ├─ PASS → Proceed to next task                          │
│     └─ FAIL → Go to step 6                                  │
│                                                             │
│  6. REPORT TO USER                                          │
│     └─ Summarize issues, explain what was tried             │
│     └─ Ask for guidance                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Context Preparation (Critical)

**Good context = good review.** Structure the review request clearly:

### Context Template

```
## Task Completed
[What was the goal? What feature/fix was implemented?]

## Changes Made
[List of files modified, functions added/changed]

## Key Decisions
[Any architectural choices, tradeoffs made]

## Areas of Concern
[Anything you're uncertain about, edge cases]
```

### Example Context

```
## Task Completed
Implemented user authentication with JWT tokens.

## Changes Made
- Added auth/jwt.py: JWT token generation and validation
- Modified routes/user.py: Added login/logout endpoints
- Updated models/user.py: Added password hashing

## Key Decisions
- Used HS256 algorithm for JWT (simpler, sufficient for single-server)
- Token expiry set to 24 hours
- Refresh tokens not implemented yet

## Areas of Concern
- Password validation regex might be too strict
- Need to verify token invalidation on logout works correctly
```

## Running the Review

### Basic Usage

```bash
python scripts/codex_review.py \
  --context "Implemented feature X with files A, B, C" \
  --code "path/to/file_or_diff.py" \
  --cd "/project/root"
```

### With Model Selection

```bash
python scripts/codex_review.py \
  --context "..." \
  --code "..." \
  --cd "/project" \
  --model "gpt-5" \
  --reasoning-effort "high"
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--context` | Yes | - | Task description and changes made |
| `--code` | Yes | - | File path (relative to --cd) or inline code/diff |
| `--cd` | Yes | - | Project root directory |
| `--model` | No | Codex default | Model. Env: `CODEX_MODEL` |
| `--reasoning-effort` | No | high | none/low/medium/high/xhigh. Env: `CODEX_REASONING_EFFORT` |
| `--log-dir` | No | ./codex-review-logs | Log directory |
| `--session-id` | No | - | Resume previous session |
| `--return-all-messages` | No | false | Include full reasoning trace |

### Output Format

```json
{
  "success": true,
  "passed": true,
  "verdict": "PASS",
  "session_id": "thread_abc123",
  "review": "Full review text from Codex...",
  "issues": [],
  "summary": "Code looks good, no critical issues found",
  "suggestions": ["Consider adding input validation"],
  "log_file": "/project/codex-review-logs/review_20250101_120000.json"
}
```

## Gate Logic Implementation

When invoking the review gate, follow this logic:

### Step 1: First Review

```bash
RESULT=$(python scripts/codex_review.py \
  --context "$CONTEXT" \
  --code "$CODE_PATH" \
  --cd "$PROJECT_DIR")

if echo "$RESULT" | jq -e '.passed == true' > /dev/null; then
  echo "✅ Review PASSED - proceeding to next task"
else
  echo "❌ Review FAILED - attempting improvements"
  # Go to Step 2
fi
```

### Step 2: Improve Based on Feedback

Read the `issues` and `review` from the result:

```python
issues = result.get("issues", [])
review = result.get("review", "")
```

Address each issue systematically:
1. Parse the issues list
2. Fix each issue in the code
3. Verify fixes locally if possible

### Step 3: Retry Review

```bash
RESULT2=$(python scripts/codex_review.py \
  --context "Addressed review feedback: $ISSUES_FIXED" \
  --code "$UPDATED_CODE_PATH" \
  --cd "$PROJECT_DIR" \
  --session-id "$SESSION_ID")

if echo "$RESULT2" | jq -e '.passed == true' > /dev/null; then
  echo "✅ Review PASSED on retry"
else
  echo "⚠️ Review still FAILING - escalating to user"
  # Go to Step 4
fi
```

### Step 4: Report to User

When the gate fails twice, report clearly:

```markdown
## Review Gate Failed

### Summary
The code review gate failed after 2 attempts.

### Original Issues (1st review)
- [List issues from first review]

### Remaining Issues (2nd review)
- [List issues from second review]

### Actions Taken
- [What was fixed between reviews]

### Recommended Next Steps
1. [Specific suggestion]
2. [Specific suggestion]

### Review Logs
- 1st review: /path/to/review_1.json
- 2nd review: /path/to/review_2.json
```

## Logging

All reviews are automatically logged to `codex-review-logs/`:

```
codex-review-logs/
├── review_20250101_120000.json
├── review_20250101_121500.json
└── ...
```

Each log contains:
- Timestamp and duration
- Context provided
- Code reviewed (truncated if large)
- Model and settings used
- Full result with verdict

## Safety Configuration

The review runs with these safe defaults:

| Setting | Value | Reason |
|---------|-------|--------|
| sandbox | read-only | Cannot modify files |
| skip-git-repo-check | enabled | Works outside git repos |

Note: `--full-auto` is intentionally NOT used to avoid overriding sandbox settings.

For HPC/Slurm environments, add `--yolo` flag if Landlock errors occur.

## Model Selection Guide

| Review Type | Recommended Model | Reasoning |
|-------------|-------------------|-----------|
| Quick sanity check | gpt-5-mini | low |
| Standard code review | gpt-5 | medium |
| Security audit | gpt-5 | high |
| Complex algorithm | gpt-5-codex | high |
| Architecture review | gpt-5 | xhigh |

## Troubleshooting

### No Response from Codex

1. Verify Codex CLI: `codex --version`
2. Check credentials: `cat ~/.codex/config.toml`
3. Test minimal command: `codex exec "hello world"`

### Verdict Not Parsed

The script attempts multiple parsing strategies:
1. JSON block in response
2. Verdict markers (PASS/FAIL, LGTM, etc.)
3. Issue count heuristics

If parsing fails, check `verdict_parsed: false` in output and review the raw `review` text.

### Review Too Slow

- Lower `--reasoning-effort` to "medium" or "low"
- Use faster model (`gpt-5-mini`)
- Reduce code size (review diffs instead of full files)

## Best Practices

1. **Be specific in context**: The more detail, the better the review
2. **Review diffs, not full files**: For changes, provide unified diff
3. **Set appropriate reasoning**: Use "high" for important code, "low" for minor changes
4. **Check logs**: Review logs help track patterns and improve process
5. **Trust but verify**: Use review as input, not absolute truth
