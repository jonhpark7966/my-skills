# Archive Schema Reference

This document describes the schema for archive entries in `web/src/content/archive/`.

## Frontmatter fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| title | string | Yes | Korean title (from upload_info.json) |
| description | string | Yes | 3-line summary in YAML multiline format |
| date | date | Yes | Date added (YYYY-MM-DD) |
| videoId | string | Yes | Uploaded video ID (with Korean subs) |
| originalVideoId | string | No | Original YouTube video ID |
| duration | string | No | "MM:SS" or "H:MM:SS" format |
| thumbnail | string | No | Custom thumbnail URL |
| chapters | array | No | List of chapter objects |
| tags | array | No | List of tag strings |
| source | string | No | Source/channel name |
| isFeatured | boolean | No | Featured on homepage (default: false) |

## Chapter object

```yaml
chapters:
  - title: "Chapter title"
    startTime: "MM:SS"
    endTime: "MM:SS"  # optional
```

## Example frontmatter

```yaml
---
title: "어떤 작업이든 수행하는 범용 로봇 훈련: Physical Intelligence"
description: |
  1. 로보틱스의 병목은 하드웨어가 아니라 "지능"이며, 파운데이션 모델/엔드투엔드 학습이 이를 풀 열쇠라는 관점을 제시한다.
  2. 핵심 난제는 일반화와 성능(긴 꼬리)이고, 이를 위해 배포를 통한 데이터 루프와 "경험으로부터의 학습(RL)"을 강조한다.
  3. VLM+액션 모델로 시작해 데이터 스케일링·가치 함수·지속적(에 가까운) 학습으로 확장하며, 특정 앱 회사로 수렴하는 함정을 피하려 한다.
date: YYYY-MM-DD  # MUST run `date +%Y-%m-%d` to get actual date
videoId: "aQX-bYqGj38"
originalVideoId: "OJCT-HGxPjk"
duration: "60:26"
source: "Sequoia Capital"
tags:
  - Physical AI
  - Robotics
  - Foundation Models
  - Reinforcement Learning
  - π0
chapters:
  - title: "지능 병목과 파운데이션 모델 미션"
    startTime: "00:00"
    endTime: "04:50"
  - title: "일반화·배포와 데이터 경제성"
    startTime: "06:59"
    endTime: "12:22"
isFeatured: true
---
```

## Body content format

After the frontmatter, include curated chapter content:

```markdown
## Chapter 1: Title (startTime-endTime)

- [MM:SS] Important point
- [MM:SS] Another key insight
  - Supporting detail

> "[MM:SS] Important quote" — Speaker Name

## Chapter 2: Title (startTime-endTime)
...
```

## Tag guidelines

Generate 3-7 meaningful tags. Categories:

1. **Topic tags**: Physical AI, Robotics, Foundation Models, Manipulation, Locomotion
2. **Technology tags**: Reinforcement Learning, VLA, Diffusion Policy, Transformer, End-to-End Learning
3. **Company/Product tags**: Physical Intelligence, π0, OpenAI, Google DeepMind
4. **People tags**: (if prominently featured) Karol Hausman, Sergey Levine

Avoid generic tags like "Video", "Archive", "YouTube".

## File naming

Use short, descriptive slugs:
- `physical-intelligence-pi0.md` ✓
- `어떤-작업이든-수행하는-범용-로봇-훈련-physical-intelligence의-karol-hausman과-tobi-springenberg.md` ✗

Derive slug from key topic, not full title.
