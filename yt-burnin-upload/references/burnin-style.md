# Burn-in subtitle style

Targets:
- Korean only (Alignment=2)
- One line per cue

## Resolution-based scaling

The script auto-detects video height and scales accordingly:

| Resolution | Height | FontSize | MarginV |
|------------|--------|----------|---------|
| 720p       | ≤720   | 12       | 35      |
| 1080p      | ≤1080  | 15       | 50      |
| 1440p      | ≤1440  | 20       | 65      |
| 4K+        | >1440  | 27       | 90      |

## Common settings (all resolutions)

- FontName: Noto Sans (use Noto Sans CJK KR for Korean if available)
- Outline: 2
- Shadow: 1
- Alignment: 2 (bottom center)

## Notes

- If Noto Sans is missing, pick a clean sans-serif installed locally.
- Ensure subtitle files contain no internal line breaks.
- The script uses ffprobe to detect resolution automatically.
