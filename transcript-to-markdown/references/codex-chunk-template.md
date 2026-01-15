# Transcript chunk to Markdown

You are given a portion of a transcript with timestamps.
Write detailed Markdown notes that preserve all important information.

Context:
- Title: <TITLE>
- Description: <DESCRIPTION><CHAPTER_CONTEXT>
- Language: <LANGUAGE>

Rules:
- Output Markdown only.
- Use the same language as the transcript.
- Every bullet point MUST include a timestamp tag: `[MM:SS]` or `[HH:MM:SS]`.
- For key statements or memorable quotes from speakers, use blockquote format:
  > "[MM:SS] Exact quote here" — Speaker Name (if known)
- Keep notes detailed; do not summarize or omit important facts.
- Use sub-bullets for supporting details.
- If a chapter title is provided, use it as the section heading.

Transcript:
<<<
<TRANSCRIPT>
>>>
