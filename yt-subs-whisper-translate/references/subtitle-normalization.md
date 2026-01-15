# Subtitle normalization (single-line cues)

Goals:
- One line per cue (no internal line breaks).
- Preserve full text; do not summarize.
- Split overly long cues into multiple cues with adjusted timings.

Heuristics:
- Merge multi-line cues by joining with a single space.
- If a cue is too long, split at punctuation or natural word boundaries.
- When splitting, divide the original cue time proportionally to text length.
- Keep a minimum cue duration (e.g., 0.8s) to avoid unreadable flashes.

Example split:
- Original: 6.0s duration, 120 chars.
- Split into two lines of 60 chars each -> two cues of ~3.0s each.

Keep timestamps strictly increasing.
