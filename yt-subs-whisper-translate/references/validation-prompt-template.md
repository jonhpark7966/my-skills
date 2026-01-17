# Subtitle Validation and Repair Task

You are validating and repairing translated subtitles.

## Video Context
- Title: <TITLE>
- Source language: <SOURCE_LANG>
- Target language: <TARGET_LANG>

## Files
- Source SRT (original): <SOURCE_SRT_PATH>
- Translated SRT (to validate): <TRANSLATED_SRT_PATH>

## Your Task

1. Read both SRT files using the Read tool
2. Compare source and translated SRT for the following issues:

### Validation Checklist

1. **Missing cues**: Every timestamp from the source must have a corresponding translation.
   Look for gaps where source has cues but translation is missing (timestamp jumps).

2. **Untranslated text**: The target language is <TARGET_LANG>. Find any cues that still
   contain <SOURCE_LANG> text (especially English words/sentences in Korean subtitles).
   Proper nouns and technical terms (like "Claude", "API", "AI") are OK to keep in English.

3. **Timestamp order**: Cues must be in chronological order with no backwards jumps.

4. **Duplicate cues**: Same timestamp with same text appearing multiple times.

5. **Empty cues**: Cues with no text content.

6. **Very long cues**: Cues longer than 80 characters may have readability issues.

### Actions

- If you find issues, use the Edit tool to fix the translated SRT file directly.
- For missing translations, translate them from the source.
- For Korean output: use formal polite style (존댓말/합쇼체).
- Keep the EXACT timestamps from the source SRT.

### Output

After validation and any fixes:
1. Report what issues you found (if any)
2. Report what fixes you made (if any)
3. Confirm the final cue count matches the source

Do NOT output the entire SRT content. Just report the issues and fixes.
