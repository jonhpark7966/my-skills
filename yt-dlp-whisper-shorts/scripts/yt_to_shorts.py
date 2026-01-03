#!/usr/bin/env python3

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlparse


@dataclasses.dataclass(frozen=True)
class SrtEntry:
    start_s: float
    end_s: float
    text: str


@dataclasses.dataclass(frozen=True)
class HighlightWindow:
    start_s: float
    end_s: float
    score: float
    topic: str
    hook: str
    why: list[str]
    edit_plan: list[str]
    excerpt: str


SRT_TS_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)


def _require_exe(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required executable not found in PATH: {name}")
    return path


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _run_capture(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return proc.stdout


def _parse_timestamp_s(ts: str) -> float:
    ts = ts.replace(",", ".")
    hh, mm, rest = ts.split(":")
    ss, ms = rest.split(".")
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0


def _format_timestamp_s(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms_total = int(round(seconds * 1000.0))
    s_total, ms = divmod(ms_total, 1000)
    hh, rem = divmod(s_total, 3600)
    mm, ss = divmod(rem, 60)
    return f"{hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}"


def _format_duration_s(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60.0
    return f"{minutes:.1f}m"


def _extract_youtube_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if host in {"youtu.be"}:
        candidate = parsed.path.strip("/").split("/")[0]
        return candidate or None

    if "youtube.com" in host or "youtube-nocookie.com" in host:
        if parsed.path == "/watch":
            q = parse_qs(parsed.query)
            candidate = (q.get("v") or [None])[0]
            return candidate
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed"}:
            return parts[1]
    return None


def _yt_dlp_get_id(url: str) -> str:
    _require_exe("yt-dlp")
    out = _run_capture(["yt-dlp", "--no-playlist", "--print", "%(id)s", "--skip-download", url])
    video_id = out.strip().splitlines()[-1].strip()
    if not video_id:
        raise RuntimeError("Failed to resolve YouTube video id via yt-dlp")
    return video_id


def _download_audio(url: str, out_dir: Path, video_id: str, extra_args: list[str]) -> Path:
    _require_exe("yt-dlp")
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = out_dir / f"{video_id}.mp3"
    if audio_path.exists():
        return audio_path

    template = str(out_dir / f"{video_id}.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-x",
        "--audio-format",
        "mp3",
        "-o",
        template,
        *extra_args,
        url,
    ]
    _run(cmd)
    if not audio_path.exists():
        candidates = sorted(out_dir.glob(f"{video_id}.*"))
        raise RuntimeError(f"Audio download succeeded but expected file not found: {audio_path} (found: {candidates})")
    return audio_path


def _transcribe_whisper(
    audio_path: Path,
    out_dir: Path,
    language: str | None,
    model: str | None,
    extra_args: list[str],
) -> Path:
    _require_exe("whisper")
    out_dir.mkdir(parents=True, exist_ok=True)
    srt_path = out_dir / f"{audio_path.stem}.srt"
    if srt_path.exists():
        return srt_path

    cmd = [
        "whisper",
        str(audio_path),
        "--output_dir",
        str(out_dir),
        "--output_format",
        "srt",
    ]
    if language:
        cmd.extend(["--language", language])
    if model:
        cmd.extend(["--model", model])
    cmd.extend(extra_args)
    _run(cmd)
    if not srt_path.exists():
        raise RuntimeError(f"Whisper finished but SRT not found: {srt_path}")
    return srt_path


def _parse_srt(path: Path) -> list[SrtEntry]:
    entries: list[SrtEntry] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if line.isdigit():
            i += 1
            if i >= len(lines):
                break
            line = lines[i].strip()

        m = SRT_TS_RE.match(line)
        if not m:
            i += 1
            continue

        start_s = _parse_timestamp_s(m.group("start"))
        end_s = _parse_timestamp_s(m.group("end"))
        i += 1

        text_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i].strip())
            i += 1

        text = " ".join(text_lines).strip()
        if text:
            entries.append(SrtEntry(start_s=start_s, end_s=end_s, text=text))
        i += 1

    if not entries:
        raise RuntimeError(f"No subtitle entries parsed from {path}")
    return entries


def _overlap_ratio(a: tuple[float, float], b: tuple[float, float]) -> float:
    a0, a1 = a
    b0, b1 = b
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    if union <= 0:
        return 0.0
    return inter / union


def _classify_topic(text: str) -> str:
    if any(k in text for k in ["변색", "태닝", "태닝 라인", "색깔", "자외선", "경계"]):
        return "변색/태닝"
    if any(k in text for k in ["셀룰러", "와이파이", "업데이트", "iOS", "핑", "5G", "로딩"]):
        return "통신/업데이트"
    if any(k in text for k in ["스크래치", "떨어", "깨", "액정", "디스플레이", "세라믹", "내구"]):
        return "내구/스크래치"
    if any(k in text for k in ["리퀴드", "글라스", "UI", "비전 프로", "가시성"]):
        return "UI/트렌드"
    return "기타"


def _score_window(text: str) -> float:
    hook_weights: dict[str, float] = {
        "이슈": 3.0,
        "난리": 2.0,
        "불량": 2.0,
        "관찰": 3.0,
        "태닝": 2.5,
        "태닝 라인": 2.5,
        "경계": 1.5,
        "안 닦": 3.0,
        "안 닦여": 3.0,
        "진짜": 1.5,
        "말이 안": 4.0,
        "대박": 2.5,
        "떨어": 2.0,
        "밟": 3.0,
        "미끄": 2.0,
        "멀쩡": 2.5,
        "스크래치": 2.0,
        "튼튼": 2.0,
        "하우징": 1.5,
        "세라믹": 1.5,
        "확실히": 1.5,
        "업데이트": 2.5,
        "개선": 3.0,
        "없어졌": 3.0,
        "추천": 2.0,
        "증명": 3.0,
        "한계": 1.5,
        "왜냐면": 1.0,
        "좋아해": 1.0,
        "호불호": 1.0,
        "비전 프로": 1.5,
    }
    problem_tokens = ["이슈", "문제", "안 되", "변색", "스크래치", "지연", "버벅", "깨"]
    resolve_tokens = ["없어졌", "개선", "추천", "증명", "추정", "해결"]
    outro_tokens = ["안녕", "댓글", "다음", "구독", "좋아요"]
    section_transition_tokens = ["다음으로", "마지막으로"]

    score = 0.0
    for kw, w in hook_weights.items():
        if kw in text:
            score += w

    if re.search(r"\d", text):
        score += 1.5
    if "?" in text or "까요" in text or "죠?" in text:
        score += 1.2

    has_problem = any(t in text for t in problem_tokens)
    has_resolve = any(t in text for t in resolve_tokens)
    if has_problem and has_resolve:
        score += 2.0

    if any(t in text for t in ["저는", "제가", "근데", "그랬더니", "봤는데"]):
        score += 1.0

    if any(t in text for t in outro_tokens):
        score -= 6.0

    for tok in section_transition_tokens:
        idx = text.find(tok)
        if idx >= 0 and idx > 15:
            score -= 3.0

    topic_groups = [
        ["변색", "태닝", "태닝 라인", "색깔", "자외선", "경계"],
        ["셀룰러", "와이파이", "업데이트", "iOS", "5G", "핑", "로딩"],
        ["스크래치", "떨어", "깨", "액정", "디스플레이", "세라믹", "내구", "하우징"],
        ["리퀴드", "글라스", "UI", "비전 프로", "가시성"],
    ]
    topic_hits = sum(1 for group in topic_groups if any(tok in text for tok in group))
    if topic_hits >= 2:
        score -= 2.5 * (topic_hits - 1)

    text_len = len(text)
    score += min(3.0, text_len / 120.0)
    score -= max(0.0, (text_len - 600) / 400.0)

    return score


def _pick_hook(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= 60:
        return text
    return text[:60].rstrip() + "…"


def _build_why(text: str) -> list[str]:
    reasons: list[str] = []
    if any(k in text for k in ["이슈", "문제", "난리"]):
        reasons.append("문제 제기(이슈)로 시작해 초반 이탈을 줄이기 좋음")
    if any(k in text for k in ["관찰", "안 닦", "없어졌", "개선", "증명"]):
        reasons.append("반전/결론(관찰·개선·증명)이 있어 15–60초 안에 완결 가능")
    if any(k in text for k in ["진짜", "말이 안", "대박", "놀라"]):
        reasons.append("리액션/감정 포인트가 강해 공유·댓글을 유도하기 좋음")
    if re.search(r"\d", text) or any(k in text for k in ["평균", "ms", "배", "개월"]):
        reasons.append("수치/기간/비교가 들어가 신뢰감과 유용성이 높음")
    if "?" in text or "까요" in text:
        reasons.append("질문형 문장이 있어 오프닝 훅(‘진짜?’) 만들기 쉬움")
    if not reasons:
        reasons.append("단일 주제로 빠르게 전개돼 쇼츠 템포에 적합")
    return reasons[:3]


def _build_edit_plan(topic: str, start_s: float, end_s: float, excerpt: str) -> list[str]:
    duration_s = max(0.0, end_s - start_s)
    open_s = min(2.0, duration_s * 0.15)
    close_s = min(2.0, duration_s * 0.15)

    base = [
        f"0–{open_s:.0f}s: 훅 자막(질문/경고/반전 예고) + 즉시 클로즈업/핵심 컷",
        f"{open_s:.0f}s–{max(open_s, duration_s - close_s):.0f}s: 핵심 전개는 점프컷으로 압축(군더더기 제거)",
        f"{max(open_s, duration_s - close_s):.0f}s–{duration_s:.0f}s: 결론/교훈 1문장 + 화면에 체크리스트/요약",
    ]

    if topic == "변색/태닝":
        return [
            "오프닝 텍스트 예시: “케이스 쓰면 폰이 ‘태닝’ 됩니다” / “오염인 줄 알았는데 안 닦임”",
            "변색 라인 보이는 순간에 서클/화살표 + 0.2초 줌인으로 ‘증거 컷’ 만들기",
            "중간이 길면 1문장 나레이션으로 연결: “자외선/케이스 노출부 때문에 경계가 생길 수 있어요”",
            *base,
        ]
    if topic == "통신/업데이트":
        return [
            "오프닝 텍스트 예시: “셀룰러 이슈… 업데이트로 해결?”",
            "‘iOS 버전’은 화면에 크게(예: 26.2) + 핑/체감 수치만 굵게 강조",
            "마지막 2초: “버벅임 느끼면 업데이트 먼저” 한 줄 CTA",
            *base,
        ]
    if topic == "내구/스크래치":
        return [
            "오프닝 텍스트 예시: “밟고 미끄러졌는데… 멀쩡함”",
            "상황 설명은 자막 1줄로 짧게, 리액션 대사는 대형 자막으로 ‘펀치’ 주기",
            "마지막에 흠집/하우징/디스플레이 클로즈업 1초 넣어 신뢰도 올리기",
            *base,
        ]
    if topic == "UI/트렌드":
        return [
            "오프닝 텍스트 예시: “iOS 26 UI, 어디서 많이 봤다 했더니…”",
            "비전 프로/반투명 UI 비교 B-roll을 끼워 넣어 ‘아하’ 포인트 강화",
            *base,
        ]
    return base


def _truncate_excerpt(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _iter_windows(entries: list[SrtEntry], min_s: float, max_s: float) -> Iterable[tuple[float, float, str]]:
    n = len(entries)
    for i in range(n):
        start_s = entries[i].start_s
        parts: list[str] = []
        for j in range(i, n):
            end_s = entries[j].end_s
            duration_s = end_s - start_s
            if duration_s > max_s:
                break
            parts.append(entries[j].text)
            if duration_s >= min_s:
                yield start_s, end_s, " ".join(parts)


def _select_highlights(
    entries: list[SrtEntry], min_s: float, max_s: float, count: int, *, max_overlap_ratio: float
) -> list[HighlightWindow]:
    candidates: list[tuple[float, float, float, str, str]] = []
    for start_s, end_s, text in _iter_windows(entries, min_s=min_s, max_s=max_s):
        text = text.strip()
        if len(text) < 30:
            continue
        score = _score_window(text)
        topic = _classify_topic(text)
        candidates.append((start_s, end_s, score, text, topic))

    candidates.sort(key=lambda t: t[2], reverse=True)

    available_topics = {t[4] for t in candidates[:500]}
    target_unique_topics = min(count, len(available_topics))

    selected: list[HighlightWindow] = []
    used_topics: set[str] = set()

    def _try_select(enforce_topic_diversity: bool) -> None:
        nonlocal selected, used_topics
        for start_s, end_s, score, text, topic in candidates:
            if any(_overlap_ratio((start_s, end_s), (s.start_s, s.end_s)) > max_overlap_ratio for s in selected):
                continue
            if enforce_topic_diversity and len(used_topics) < target_unique_topics and topic in used_topics:
                continue

            excerpt = _truncate_excerpt(text, max_chars=260)
            hook = _pick_hook(excerpt)
            why = _build_why(text)
            edit_plan = _build_edit_plan(topic, start_s, end_s, excerpt)
            selected.append(
                HighlightWindow(
                    start_s=start_s,
                    end_s=end_s,
                    score=score,
                    topic=topic,
                    hook=hook,
                    why=why,
                    edit_plan=edit_plan,
                    excerpt=excerpt,
                )
            )
            used_topics.add(topic)
            if len(selected) >= count:
                return

    _try_select(enforce_topic_diversity=True)
    if len(selected) < count:
        _try_select(enforce_topic_diversity=False)

    if not selected:
        raise RuntimeError("No suitable highlight segments found (try lowering --min-sec or increasing --max-sec)")
    return selected


def _write_outputs(
    out_dir: Path,
    url: str,
    video_id: str,
    audio_path: Path | None,
    srt_path: Path,
    *,
    min_sec: float,
    max_sec: float,
    count: int,
    max_overlap_ratio: float,
) -> tuple[Path, Path]:
    entries = _parse_srt(srt_path)
    highlights = _select_highlights(entries, min_s=min_sec, max_s=max_sec, count=count, max_overlap_ratio=max_overlap_ratio)

    payload = {
        "url": url,
        "video_id": video_id,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "audio_file": str(audio_path) if audio_path else None,
        "srt_file": str(srt_path),
        "min_sec": min_sec,
        "max_sec": max_sec,
        "count": count,
        "max_overlap_ratio": max_overlap_ratio,
        "highlights": [
            {
                "start": _format_timestamp_s(h.start_s),
                "end": _format_timestamp_s(h.end_s),
                "duration_sec": round(h.end_s - h.start_s, 3),
                "score": round(h.score, 3),
                "topic": h.topic,
                "hook": h.hook,
                "why": h.why,
                "edit_plan": h.edit_plan,
                "excerpt": h.excerpt,
            }
            for h in highlights
        ],
    }

    json_path = out_dir / "highlights.json"
    md_path = out_dir / "highlights.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md_lines: list[str] = []
    md_lines.append(f"# Shorts highlight suggestions ({video_id})")
    md_lines.append("")
    md_lines.append(f"- URL: {url}")
    md_lines.append(f"- SRT: {srt_path}")
    if audio_path:
        md_lines.append(f"- Audio: {audio_path}")
    md_lines.append(f"- Range: {min_sec:.0f}s–{max_sec:.0f}s, Picks: {count}")
    md_lines.append(f"- Max overlap ratio: {max_overlap_ratio:.2f}")
    md_lines.append("")

    for idx, h in enumerate(payload["highlights"], start=1):
        md_lines.append(f"## Pick {idx}: {h['topic']}")
        md_lines.append("")
        md_lines.append(
            f"- Time: `{h['start']}–{h['end']}` ({_format_duration_s(h['duration_sec'])}), score `{h['score']}`"
        )
        md_lines.append(f"- Hook (on-screen): {h['hook']}")
        md_lines.append("- Why it works:")
        for reason in h["why"]:
            md_lines.append(f"  - {reason}")
        md_lines.append("- Edit plan:")
        for step in h["edit_plan"][:6]:
            md_lines.append(f"  - {step}")
        md_lines.append(f"- Transcript excerpt: {h['excerpt']}")
        md_lines.append("")

    md_path.write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")
    return md_path, json_path


def _split_csv_list(value: str) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="yt_to_shorts.py",
        formatter_class=argparse.RawTextHelpFormatter,
        description=textwrap.dedent(
            """\
            Download YouTube audio with yt-dlp, transcribe with Whisper, and recommend Shorts-ready highlight segments.

            Outputs (by default):
              ./yt_shorts/<video_id>/<video_id>.mp3
              ./yt_shorts/<video_id>/<video_id>.srt
              ./yt_shorts/<video_id>/highlights.md
              ./yt_shorts/<video_id>/highlights.json
            """
        ),
    )
    parser.add_argument("url", help="YouTube URL (watch/shorts/youtu.be supported)")
    parser.add_argument("--output-root", default="yt_shorts", help="Root directory for outputs (default: yt_shorts)")
    parser.add_argument("--language", default=None, help="Whisper language code (e.g., ko). Omit to let Whisper detect.")
    parser.add_argument("--model", default=None, help="Whisper model name (omit to use Whisper default)")
    parser.add_argument("--min-sec", dest="min_sec", type=float, default=15.0, help="Minimum segment length in seconds")
    parser.add_argument("--max-sec", dest="max_sec", type=float, default=60.0, help="Maximum segment length in seconds")
    parser.add_argument("--count", type=int, default=3, help="How many highlight segments to recommend")
    parser.add_argument(
        "--max-overlap",
        dest="max_overlap",
        type=float,
        default=0.25,
        help="Max allowed overlap ratio between picks (0.0–1.0, default: 0.25)",
    )
    parser.add_argument("--no-download", action="store_true", help="Skip yt-dlp download (requires existing audio/SRT)")
    parser.add_argument("--no-transcribe", action="store_true", help="Skip Whisper transcription (requires existing SRT)")
    parser.add_argument("--audio-file", default=None, help="Use an existing audio file instead of downloading")
    parser.add_argument("--srt-file", default=None, help="Use an existing SRT file instead of running Whisper")
    parser.add_argument(
        "--yt-dlp-args",
        default="",
        help="Extra yt-dlp args as a comma-separated string (e.g., \"--cookies,cookies.txt\")",
    )
    parser.add_argument(
        "--whisper-args",
        default="",
        help="Extra whisper args as a comma-separated string (e.g., \"--task,transcribe\")",
    )

    args = parser.parse_args()

    if args.min_sec <= 0 or args.max_sec <= 0:
        raise SystemExit("--min-sec and --max-sec must be positive")
    if args.min_sec > args.max_sec:
        raise SystemExit("--min-sec must be <= --max-sec")
    if args.count <= 0:
        raise SystemExit("--count must be >= 1")
    if not (0.0 <= args.max_overlap <= 1.0):
        raise SystemExit("--max-overlap must be between 0.0 and 1.0")

    video_id = _extract_youtube_id(args.url) or _yt_dlp_get_id(args.url)
    out_dir = Path(args.output_root) / video_id
    out_dir.mkdir(parents=True, exist_ok=True)

    yt_dlp_args = _split_csv_list(args.yt_dlp_args)
    whisper_args = _split_csv_list(args.whisper_args)

    audio_path: Path | None = None
    srt_path: Path | None = None

    if args.srt_file:
        srt_path = Path(args.srt_file)
        if not srt_path.exists():
            raise SystemExit(f"--srt-file not found: {srt_path}")
    if args.audio_file:
        audio_path = Path(args.audio_file)
        if not audio_path.exists():
            raise SystemExit(f"--audio-file not found: {audio_path}")

    if not args.no_download and not audio_path and not srt_path:
        audio_path = _download_audio(args.url, out_dir, video_id, extra_args=yt_dlp_args)

    if not srt_path and not args.no_transcribe:
        if not audio_path:
            raise SystemExit("Need audio to transcribe (provide --audio-file or run without --no-download)")
        srt_path = _transcribe_whisper(
            audio_path=audio_path,
            out_dir=out_dir,
            language=args.language,
            model=args.model,
            extra_args=whisper_args,
        )

    if not srt_path:
        inferred = out_dir / f"{video_id}.srt"
        if inferred.exists():
            srt_path = inferred
        else:
            raise SystemExit("No SRT available (provide --srt-file or run without --no-transcribe)")

    md_path, json_path = _write_outputs(
        out_dir,
        url=args.url,
        video_id=video_id,
        audio_path=audio_path,
        srt_path=srt_path,
        min_sec=args.min_sec,
        max_sec=args.max_sec,
        count=args.count,
        max_overlap_ratio=args.max_overlap,
    )
    print(f"[OK] Wrote: {md_path}")
    print(f"[OK] Wrote: {json_path}")
