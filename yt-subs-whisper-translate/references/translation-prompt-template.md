# Codex translation prompt template

Fill in the placeholders and write the chunk SRT at the end.
Save each prompt to a file and call:

`codex exec --skip-git-repo-check "@file PROMPT"`

---

You are translating subtitles from <SOURCE_LANG> to <TARGET_LANG>.

Video context:
- Title: <TITLE>
- Description: <DESCRIPTION>
- Additional context: <EXTRA_CONTEXT>

Rules:
- CRITICAL: Output the translated SRT directly as text in your response.
  Do NOT use any tools, shell commands, or file operations. Do NOT write
  to any files. Just output the SRT text below.
- Output valid SRT only (no commentary).
- CRITICAL: Keep the EXACT timestamps from the input SRT. Do NOT modify,
  shift, or reset timestamps. The output must use the same absolute
  timestamps as the input (e.g., if input starts at 00:02:30, output must
  also start at 00:02:30, NOT 00:00:00).
- If splitting a cue, divide the original time range proportionally.
- One text line per cue. No line breaks inside a cue.
- Do not summarize, shorten, or omit content. Translate ALL cues.
- IMPORTANT: If a proper noun in the input differs from the Title/Description
  (e.g., "NIO" vs "NEO"), use the spelling from the Title/Description.
  The video context is authoritative for proper nouns.
- Break cues at natural semantic boundaries (phrases, clauses).
  Avoid splitting in the middle of a noun phrase or verb phrase.
- For Korean output: use formal polite style (존댓말/합쇼체). End
  sentences with -습니다/-ㅂ니다, -입니다, etc. Avoid casual endings.

Input SRT:
<<<
<CHUNK_SRT>
>>>

Output SRT:
<<<
<WRITE_SRT_HERE>
>>>
