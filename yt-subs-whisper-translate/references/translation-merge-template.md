# Codex merge/repair prompt template

Use this after chunk translations to reconcile overlaps and fix missing lines.

---

You are improving subtitles translated from <SOURCE_LANG> to <TARGET_LANG>.

Video context:
- Title: <TITLE>
- Description: <DESCRIPTION>
- Additional context: <EXTRA_CONTEXT>

Rules:
- CRITICAL: Output the translated SRT directly as text in your response.
  Do NOT use any tools, shell commands, or file operations. Do NOT write
  to any files. Just output the SRT text below.
- Output valid SRT only (no commentary).
- Use the timestamps from the source SRT. Do not add or remove cues.
- One text line per cue. No line breaks inside a cue.
- Do not summarize, shorten, or omit content.
- Use the candidate translation when it is correct, but fix missing or broken lines.
- Ensure cues break at natural semantic boundaries (phrases, clauses).
- For Korean output: use formal polite style (존댓말/합쇼체). End
  sentences with -습니다/-ㅂ니다, -입니다, etc. Avoid casual endings.

Source SRT:
<<<
<CHUNK_SRT>
>>>

Candidate translation SRT:
<<<
<CANDIDATE_SRT>
>>>

Output SRT:
<<<
<WRITE_SRT_HERE>
>>>
