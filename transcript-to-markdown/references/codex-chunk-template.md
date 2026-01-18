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
- For key statements or memorable quotes, use blockquote format:
  > "[MM:SS] Exact quote here"
- Keep notes detailed; do not summarize or omit important facts.
- Use sub-bullets for supporting details.
- If a chapter title is provided, use it as the section heading.

Minimum output requirements:
- Generate at least 15 bullet points per 10 minutes of transcript.
- Include at least 1-2 blockquotes per 10 minutes for key statements.
- Do NOT compress or merge multiple ideas into a single bullet point.
- Each distinct idea or fact deserves its own bullet point.

Transcript:
<<<
<TRANSCRIPT>
>>>
