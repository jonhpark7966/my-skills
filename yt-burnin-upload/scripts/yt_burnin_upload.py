#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _require_exe(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required executable not found in PATH: {name}")
    return path


def _run(cmd: list[str], capture: bool = False) -> str:
    if capture:
        proc = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return proc.stdout
    subprocess.run(cmd, check=True)
    return ""


def _parse_json_from_output(output: str, context: str) -> dict:
    payload = output.strip()
    if not payload:
        raise RuntimeError(f"{context} returned empty output")
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        pass
    start = payload.find("{")
    end = payload.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError(f"{context} output was not valid JSON")
    try:
        return json.loads(payload[start : end + 1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{context} output was not valid JSON") from exc


def _yt_dlp_id(url: str) -> str:
    _require_exe("yt-dlp")
    out = _run(
        ["yt-dlp", "--no-playlist", "--quiet", "--no-warnings", "--print", "%(id)s", "--skip-download", url],
        capture=True,
    )
    video_id = out.strip().splitlines()[-1].strip()
    if not video_id:
        raise RuntimeError("Failed to resolve YouTube video id")
    return video_id


def _yt_dlp_meta(url: str, output_path: Path) -> dict:
    _require_exe("yt-dlp")
    out = _run(
        ["yt-dlp", "--no-playlist", "--dump-json", "--skip-download", "--quiet", "--no-warnings", url],
        capture=True,
    )
    output_path.write_text(out, encoding="utf-8")
    return _parse_json_from_output(out, "yt-dlp metadata")


def _download_best(url: str, out_dir: Path) -> Path:
    _require_exe("yt-dlp")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "source.mp4"
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f",
        "bv*+ba/b",
        "--merge-output-format",
        "mp4",
        "-o",
        str(out_path),
        url,
    ]
    _run(cmd)
    if not out_path.exists():
        raise RuntimeError(f"Download finished but {out_path} not found")
    return out_path


def _escape_sub_path(path: Path) -> str:
    escaped = path.as_posix().replace("\\", "/")
    escaped = escaped.replace(":", "\\:").replace("'", "\\'")
    return escaped


def _get_video_height(video_path: Path) -> int:
    """Get video height using ffprobe."""
    _require_exe("ffprobe")
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=height",
        "-of", "csv=p=0",
        str(video_path),
    ]
    try:
        out = _run(cmd, capture=True)
        return int(out.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 1080  # default to 1080p


def _get_font_size_for_resolution(height: int) -> int:
    """Return appropriate font size based on video height.

    Target: FHD (1080p) = 12pt, scale proportionally for other resolutions.
    """
    # Base: 12pt at 1080p
    base_size = 12
    base_height = 1080
    # Scale linearly with resolution
    scaled = int(round(base_size * height / base_height))
    # Clamp to reasonable range
    return max(10, min(scaled, 36))


def _get_margin_for_resolution(height: int) -> int:
    """Return appropriate bottom margin based on video height.

    Target: FHD (1080p) = 20px from bottom, scale proportionally.
    """
    # Base: 20px at 1080p (closer to bottom edge)
    base_margin = 20
    base_height = 1080
    scaled = int(round(base_margin * height / base_height))
    return max(10, min(scaled, 50))


def _burn_in(
    video_path: Path,
    out_path: Path,
    ko_srt: Path,
) -> None:
    _require_exe("ffmpeg")

    # Detect resolution and scale font
    height = _get_video_height(video_path)
    font_size = _get_font_size_for_resolution(height)
    margin_v = _get_margin_for_resolution(height)

    print(f"Burn-in settings: height={height}px, font_size={font_size}pt, margin_v={margin_v}px", file=sys.stderr)

    filters = []
    ko_path = _escape_sub_path(ko_srt)
    # ASS style: Alignment=2 is bottom-center, WrapStyle=2 disables smart wrapping
    # BorderStyle=1 is outline + shadow
    force_style = (
        f"FontName=Noto Sans CJK KR,"
        f"FontSize={font_size},"
        f"PrimaryColour=&HFFFFFF,"
        f"OutlineColour=&H000000,"
        f"Outline=2,"
        f"Shadow=1,"
        f"BorderStyle=1,"
        f"Alignment=2,"
        f"MarginV={margin_v},"
        f"WrapStyle=2"
    )
    filters.append(f"subtitles='{ko_path}':force_style='{force_style}'")
    vf = ",".join(filters)

    # Check for NVENC support
    nvenc_available = False
    try:
        check = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True,
            text=True,
        )
        nvenc_available = "h264_nvenc" in check.stdout
    except Exception:
        pass

    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-i",
        str(video_path),
        "-vf",
        vf,
    ]

    if nvenc_available:
        # Use NVIDIA GPU encoding (much faster)
        print("Using NVENC GPU encoding", file=sys.stderr)
        cmd.extend([
            "-c:v", "h264_nvenc",
            "-preset", "p4",  # Balanced speed/quality
            "-cq", "23",  # Constant quality
        ])
    else:
        print("NVENC not available, using CPU encoding", file=sys.stderr)
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
        ])

    cmd.extend([
        "-c:a", "copy",
        str(out_path),
    ])
    try:
        _run(cmd)
    except subprocess.CalledProcessError as exc:
        error_msg = (
            f"ffmpeg burn-in failed.\n"
            f"Possible causes:\n"
            f"  - Font 'Noto Sans CJK KR' not installed (install via: sudo apt install fonts-noto-cjk)\n"
            f"  - Invalid SRT file format (check {ko_srt})\n"
            f"  - Insufficient disk space\n"
            f"  - Video codec not supported\n"
            f"Command was: {' '.join(cmd)}"
        )
        raise RuntimeError(error_msg) from exc


def _translate_metadata(title: str, description: str, prompt_path: Path, dry_run: bool) -> dict:
    prompt = (
        "Translate the following metadata to Korean.\n"
        "Rules:\n"
        "- Preserve proper nouns and product names.\n"
        "- Do not add new content.\n"
        "- Output strict JSON with keys: title, description.\n\n"
        f"Title: {title}\n"
        f"Description: {description}\n"
    )
    prompt_path.write_text(prompt, encoding="utf-8")

    if dry_run:
        return {"title": title, "description": description}

    _require_exe("codex")
    output_path = prompt_path.with_suffix(".response.json")
    cmd = ["codex", "exec", "--skip-git-repo-check", "-o", str(output_path), f"@file {prompt_path}"]
    _run(cmd)
    out = output_path.read_text(encoding="utf-8").strip()
    try:
        return _parse_json_from_output(out, "Codex metadata translation")
    except RuntimeError as exc:
        print(f"Warning: {exc}. Falling back to original metadata.", file=sys.stderr)
        return {"title": title, "description": description}


def _upload_video(
    video_path: Path,
    title: str,
    description: str,
    client_secret: Path,
    token_path: Path,
    privacy_status: str,
    dry_run: bool,
) -> None:
    if dry_run:
        return

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise RuntimeError("Missing google-api-python-client dependencies") from exc

    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), scopes)
    creds = flow.run_local_server(port=0)
    token_path.write_text(creds.to_json(), encoding="utf-8")

    youtube = build("youtube", "v3", credentials=creds)
    request_body = {
        "snippet": {
            "title": title,
            "description": description,
        },
        "status": {"privacyStatus": privacy_status},
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)
    request.execute()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download, burn in subtitles, and upload via YouTube Data API.")
    parser.add_argument("url", nargs="?", help="YouTube URL")
    parser.add_argument("--out-dir", type=Path, help="Output directory")
    parser.add_argument("--video-id", help="Override video id (skip yt-dlp id lookup)")
    parser.add_argument("--input-video", type=Path, help="Use an existing video file (skip download)")
    parser.add_argument("--ko-srt", type=Path, help="Korean subtitle SRT (required for burn-in)")
    parser.add_argument("--meta", type=Path, help="Existing metadata JSON (skip yt-dlp)")
    parser.add_argument("--client-secret", type=Path, help="OAuth client secret JSON (TODO)")
    parser.add_argument("--token", type=Path, default=Path("token.json"), help="Token cache path")
    parser.add_argument("--upload", action="store_true", help="Upload via YouTube Data API")
    parser.add_argument("--privacy", default="unlisted", help="Privacy status (default unlisted)")
    parser.add_argument("--dry-run", action="store_true", help="Skip external commands")
    args = parser.parse_args()

    if not args.input_video and not args.url:
        parser.error("Provide a URL or --input-video")

    if args.ko_srt is None:
        parser.error(
            "--ko-srt is required.\n"
            "If you don't have a Korean subtitle file yet, use yt-subs-whisper-translate first:\n"
            "  python3 yt-subs-whisper-translate/scripts/yt_subs_whisper_translate.py \"<URL>\"\n"
            "This will generate ko.srt in the output folder."
        )
    if not args.ko_srt.exists():
        raise RuntimeError(
            f"Korean SRT not found: {args.ko_srt}\n"
            f"If you need to generate Korean subtitles, use yt-subs-whisper-translate first:\n"
            f"  python3 yt-subs-whisper-translate/scripts/yt_subs_whisper_translate.py \"<URL>\"\n"
            f"This will create ko.srt that you can use with --ko-srt."
        )

    video_id = args.video_id
    meta_path = args.meta
    meta = {}

    if not args.input_video and args.url:
        if not video_id:
            video_id = _yt_dlp_id(args.url)
        out_dir = args.out_dir or Path("yt_burnin") / video_id
        out_dir.mkdir(parents=True, exist_ok=True)
        meta_path = meta_path or (out_dir / "meta.json")
        if not args.dry_run:
            meta = _yt_dlp_meta(args.url, meta_path)
    else:
        if not args.out_dir:
            parser.error("--out-dir is required when using --input-video")
        out_dir = args.out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

    if meta_path and meta_path.exists() and not meta:
        try:
            meta = _parse_json_from_output(meta_path.read_text(encoding="utf-8"), "metadata file")
        except RuntimeError:
            meta = {}

    if args.input_video:
        video_path = args.input_video
    else:
        video_path = out_dir / "source.mp4"
        if not args.dry_run:
            video_path = _download_best(args.url, out_dir)

    burnin_path = out_dir / "burnin.mp4"

    if not args.dry_run:
        _burn_in(video_path, burnin_path, args.ko_srt)

    title = meta.get("title", "")
    description = meta.get("description", "")
    prompt_path = out_dir / "translate_metadata.prompt.txt"
    translated = _translate_metadata(title, description, prompt_path, args.dry_run)
    ko_title = translated.get("title", title)
    ko_description = translated.get("description", description)

    if args.upload:
        if not args.client_secret:
            raise RuntimeError("OAuth client secret path is required for upload")
        _upload_video(
            burnin_path,
            ko_title,
            ko_description,
            args.client_secret,
            args.token,
            args.privacy,
            args.dry_run,
        )
    else:
        metadata_out = out_dir / "metadata_ko.json"
        metadata_out.write_text(
            json.dumps({"title": ko_title, "description": ko_description}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
