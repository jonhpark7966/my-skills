# Burn-in subtitle style

Targets:
- Dual subtitles: Korean (bottom) + English (above Korean)
- One line per cue
- Color-coded for readability

## Color scheme

| Language | Hex Code | ASS BGR | Description |
|----------|----------|---------|-------------|
| English  | #43d6a9  | &HA9D643 | Cyan/teal   |
| Korean   | #fe721a  | &H1A72FE | Orange      |

## Fixed settings (all resolutions)

FFmpeg subtitles filter handles scaling internally, so we use fixed values:

| Setting | Value | Notes |
|---------|-------|-------|
| FontSize | 12pt | Fixed for all resolutions |
| Korean MarginV | 20px | Bottom margin |
| English MarginV | 38px | Above Korean (20 + 12*1.5) |
| FontName (Korean) | Noto Sans CJK KR | |
| FontName (English) | Noto Sans | |
| Outline | 2 | |
| Shadow | 1 | |
| Alignment | 2 | Bottom center |

## Notes

- If Noto Sans is missing, pick a clean sans-serif installed locally.
- Ensure subtitle files contain no internal line breaks.
- English subtitle (`--en-srt`) is required for dual-subtitle burn-in.
- No resolution-based scaling - FFmpeg handles this internally.
