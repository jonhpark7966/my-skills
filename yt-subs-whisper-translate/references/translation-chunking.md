# Translation chunking and merging

Chunking rules:
- Target chunk length: ~180s.
- Overlap: 30s for better context.
- Each chunk keeps original timestamps; do not rebase times.

Chunk construction (conceptual):
1. Sort cues by start time.
2. For each chunk, choose a time window [T, T+180s].
3. Include all cues that overlap the window.
4. Next chunk starts at T+180s-30s.

Parallel translation:
- Create one prompt file per chunk using the template in
  `references/translation-prompt-template.md`.
- Run Codex CLI on all chunks in parallel (e.g., `xargs -P 4`).
- Use `gpt-5.2` with reasoning effort `medium` for the chunk translation pass.

Merging translated chunks:
1. Concatenate all translated cues.
2. Sort by start time.
3. De-duplicate within overlap regions:
   - If cues share the same time range, keep the later chunk's version.
   - If cues overlap with similar text, keep one copy.
4. Reindex cues sequentially.

Use the overlap to resolve wording differences. If two cues conflict,
prefer the later chunk (it has more forward context).

Repair pass (recommended):
- After merging, run a second pass with `gpt-5.2` and reasoning effort `high` using
  `references/translation-merge-template.md` to fix missing lines and
  formatting issues.
