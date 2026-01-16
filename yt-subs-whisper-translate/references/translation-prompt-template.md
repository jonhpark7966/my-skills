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
- Output valid SRT only (no commentary).
- Keep timestamps aligned with the input. If splitting a cue, divide the
  original time range proportionally.
- One text line per cue. No line breaks inside a cue.
- Do not summarize, shorten, or omit content.
- Preserve names and terminology. Use the video context to handle
  proper nouns.
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
