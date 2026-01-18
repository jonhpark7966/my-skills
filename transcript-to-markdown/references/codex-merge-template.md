# Merge chunk outputs into final Markdown

You are given multiple Markdown chunks from a transcript.
Merge them into a single, well-structured document.

Context:
- Title: <TITLE>
- Description: <DESCRIPTION>
- Language: <LANGUAGE>

Rules:
- Output Markdown only.
- Use the same language as the chunks.
- Start with: `# <TITLE>`
- Then include exactly 3 summary lines as a numbered list (1. 2. 3.).
- After that, organize content into chapters:
  `## Chapter N: <Topic> (<MM:SS>-<MM:SS>)`
- Under each chapter, use bullet points with timestamp tags:
  `- [MM:SS] <Detailed note>`
- Preserve all blockquotes (key statements) from the chunks:
  > "[MM:SS] Quote"
- Maintain chronological order by timestamps.
- Do not add sections beyond summary and chapters.

Information retention (CRITICAL):
- ONLY remove exact duplicates from overlapping regions (same timestamp, same content).
- Do NOT summarize or condense non-duplicate content.
- Each chunk's bullet points must be preserved at least 80%.
- Each 10-minute section must have at least 15 bullet points.
- Total output length must be at least 70% of combined input length.
- When in doubt, KEEP the information rather than omitting it.

Chunk outputs:
<<<
<CHUNK_OUTPUTS>
>>>
