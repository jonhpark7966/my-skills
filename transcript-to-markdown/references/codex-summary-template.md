# Transcript-to-Markdown prompt

You are given a transcript with timestamps.
Write a detailed Markdown summary that preserves as much information as possible.

Rules:
- Output Markdown only.
- Use the same language as the transcript: <LANGUAGE>.
- Start with a title line: "# <TITLE>".
- Then include exactly 3 summary lines as numbered list items.
- After that, include only chapter sections in this format:
  "## Chapter N: <Topic> (<MM:SS>-<MM:SS>)"
- Under each chapter, use bullet points with timestamp tags:
  "- [MM:SS] <Detailed note>"
- Keep notes detailed; do not omit important information.
- Do not add extra sections beyond summary and chapters.

Transcript:
<<<
<TRANSCRIPT>
>>>
