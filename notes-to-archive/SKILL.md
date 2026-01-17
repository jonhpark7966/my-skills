---
name: notes-to-archive
description: Convert verbose notes.md from transcript-to-markdown into a curated web archive entry. Selects important points, generates meaningful tags, and creates a PR to the web repository.
---

# notes-to-archive

## Overview

This skill transforms verbose transcript notes into curated archive entries for the sudoremove.com web site. It involves intelligent content curation, not just data copying.

## When to use

Use this skill when you have:
- A processed video folder in `youtube-storage/videos/{video_id}/`
- With `notes.md`, `upload_info.json`, and `meta.json` files
- And want to add it to the web archive at `web/src/content/archive/ko/`

## Workflow

1. **Read source files** from the video folder
2. **Curate content** - select important points, improve formatting
3. **Generate tags** - meaningful tags based on content
4. **Create archive markdown** - following the schema
5. **Git operations** - branch, commit, push, create PR

## Step 1: Read source files

Required files in the video folder:
- `notes.md` - verbose transcript notes (from transcript-to-markdown)
- `upload_info.json` - contains `video_id`, `title` (Korean), `url`
- `meta.json` - contains `duration`, `uploader`, `channel`

## Step 2: Curate content

This is the key step. Do NOT copy notes.md verbatim. Instead:

### Select important bullet points
- Keep ~30-50% of the original bullets (most important ones)
- Prioritize: key insights, main arguments, memorable quotes
- Remove: repetitive points, minor details, transitional statements

### CRITICAL: Preserve timestamps
**Every bullet point MUST start with `[MM:SS]` timestamp.** This is essential for video navigation.

- ✅ CORRECT: `- [00:49] 카롤·토비와 함께 로보틱스를 위한 파운데이션 모델...`
- ❌ WRONG: `- 카롤·토비와 함께 로보틱스를 위한 파운데이션 모델...`
- ❌ WRONG: `- **아이디어**: AI 주제의 일간 뉴스레터...` (no timestamp)

Do NOT summarize multiple timestamps into one bullet. Each bullet = one timestamp from original notes.

### Improve formatting
- Clean up bullet text for readability (but keep the `[MM:SS]` prefix!)
- Keep blockquotes for truly important quotes only (with timestamps)

### Chapter handling
- Keep all chapters from notes.md
- But reduce content within each chapter
- Simplify chapter titles if too verbose

## Step 3: Generate meaningful tags

Generate 3-7 relevant tags based on content. Examples:
- Topic tags: "Physical AI", "Robotics", "Foundation Models"
- Technology tags: "Reinforcement Learning", "VLA", "Diffusion Policy"
- Company/person tags: "Physical Intelligence", "π0"

Do NOT use generic tags like "Video Archive".

## Step 4: Create archive markdown

Follow the schema in `references/archive-schema.md`.

Frontmatter structure:
```yaml
---
title: "Korean title from upload_info.json"
description: |
  1. First summary line
  2. Second summary line
  3. Third summary line
date: YYYY-MM-DD (today)
videoId: "uploaded_video_id"
originalVideoId: "original_youtube_id"
duration: "MM:SS" or "H:MM:SS"
source: "Channel name"
tags:
  - Tag1
  - Tag2
chapters:
  - title: "Chapter title"
    startTime: "MM:SS"
    endTime: "MM:SS"
isFeatured: false
---
```

Body: Curated chapter content (NOT the full notes.md)

## Step 5: Git operations

1. **Check for duplicates** - search existing files for same `originalVideoId`
2. **Generate filename** - short, descriptive slug (e.g., `physical-intelligence-pi0.md`)
3. **Create branch** - `archive/{slug}`
4. **Write file** to `web/src/content/archive/ko/{slug}.md`
5. **Commit** with message `Add archive: {short title}`
6. **Push** to origin
7. **Create PR** with summary

PR body format:
```
## Summary
- Add video archive: {title}
- Video ID: {videoId}
- Original: {originalVideoId}

## Content preview
{first 3 bullet points from the curated content}

🤖 Generated with notes-to-archive skill
```

## Example transformation

### Before (notes.md excerpt):
```markdown
## Chapter 1: 지능 병목과 파운데이션 모델 미션 (00:00-04:50)
- [00:00] 범용 학습 알고리즘에 데이터를 넣으면 "어째서인지" 이해하고 이전 방식보다 더 잘해내는 현상이 놀랍다고 언급.
- [00:17] 이 현상이 로봇뿐 아니라 비전·언어·소리 등 다양한 모달리티 전반에서 관찰된다고 강조.
- [00:25] "실제로 작동한다"는 사실 자체가 충격적이라고 말함.
> "[00:29] 그리고 실제로 작동한다는 것 자체가 정말로 충격적일 정도입니다" — (발언자 미상)
- [00:49] 카롤·토비(Physical Intelligence)와 함께 로보틱스를 위한 파운데이션 모델을 만드는 접근을 다룬다고 소개.
- [00:56] 로보틱스를 인식·계획·제어로 나누는 고전적 접근이 왜 근본적으로 잘못됐는지 논의 예고.
- [01:03] 엔드투엔드 강화학습 기반 학습이 실제 배치를 가능하게 만든다는 주장 예고.
...
```

### After (curated archive):
```markdown
## Chapter 1: 지능 병목과 파운데이션 모델 미션 (00:00-04:50)

- [00:00] 범용 학습 알고리즘에 데이터를 넣으면 "어째서인지" 이해하고 이전 방식보다 더 잘해내는 현상이 놀랍다
- [00:49] 카롤·토비(Physical Intelligence)와 함께 로보틱스를 위한 파운데이션 모델을 만드는 접근을 다룸
- [01:43] 회사 미션: "어떤 로봇이든 어떤 과업이든 수행"할 수 있는 로보틱 파운데이션 모델 개발
- [03:22] 로봇공학의 병목은 하드웨어가 아니라 "지능"이었다는 관점을 제시

> "[00:29] 그리고 실제로 작동한다는 것 자체가 정말로 충격적일 정도입니다" — Karol Hausman
```

## Paths

- Video source: `/home/jonhpark/workspace/youtube-storage/videos/{video_id}/`
- Web archive: `/home/jonhpark/workspace/web/src/content/archive/ko/`
- Web repo for git: `/home/jonhpark/workspace/web/`

## Important notes

- Always check for existing archive with same originalVideoId before creating
- Use Korean title from upload_info.json (it's already translated)
- Keep the 3-line summary from notes.md (it's already good)
- isFeatured should be false by default (human decides later)
- After creating PR, switch web repo back to main branch
