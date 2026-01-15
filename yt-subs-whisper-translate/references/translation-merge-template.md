# Codex merge/repair prompt template

Use this after chunk translations to reconcile overlaps and fix missing lines.

---

You are improving subtitles translated from <SOURCE_LANG> to <TARGET_LANG>.

Video context:
- Title: <TITLE>
- Description: <DESCRIPTION>
- Additional context: <EXTRA_CONTEXT>

Rules:
- Output valid SRT only (no commentary).
- Use the timestamps from the source SRT. Do not add or remove cues.
- One text line per cue. No line breaks inside a cue.
- Do not summarize, shorten, or omit content.
- Use the candidate translation when it is correct, but fix missing or broken lines.

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
