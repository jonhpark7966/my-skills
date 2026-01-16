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
- Remove duplicate content from overlapping regions.
- Maintain chronological order by timestamps.
- Do not omit important information; keep notes detailed.
- Do not add sections beyond summary and chapters.

Chunk outputs:
<<<
<CHUNK_OUTPUTS>
>>>
