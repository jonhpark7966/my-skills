#!/usr/bin/env python3
"""
Codex Review Gate Script for Claude Code.
Requests code review from Codex CLI and returns structured pass/fail verdict.
"""
from __future__ import annotations

import json
import os
import sys
import queue
import subprocess
import threading
import time
import shutil
import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import Generator, List, Optional, Dict, Any


# ============================================================================
# Windows Compatibility (from collaborating-with-codex)
# ============================================================================

def _get_windows_npm_paths() -> List[Path]:
    """Return candidate directories for npm global installs on Windows."""
    if os.name != "nt":
        return []
    paths: List[Path] = []
    env = os.environ
    if prefix := env.get("NPM_CONFIG_PREFIX") or env.get("npm_config_prefix"):
        paths.append(Path(prefix))
    if appdata := env.get("APPDATA"):
        paths.append(Path(appdata) / "npm")
    if localappdata := env.get("LOCALAPPDATA"):
        paths.append(Path(localappdata) / "npm")
    if programfiles := env.get("ProgramFiles"):
        paths.append(Path(programfiles) / "nodejs")
    return paths


def _augment_path_env(env: dict) -> None:
    """Prepend npm global directories to PATH if missing."""
    if os.name != "nt":
        return
    path_key = next((k for k in env if k.upper() == "PATH"), "PATH")
    path_entries = [p for p in env.get(path_key, "").split(os.pathsep) if p]
    lower_set = {p.lower() for p in path_entries}
    for candidate in _get_windows_npm_paths():
        if candidate.is_dir() and str(candidate).lower() not in lower_set:
            path_entries.insert(0, str(candidate))
            lower_set.add(str(candidate).lower())
    env[path_key] = os.pathsep.join(path_entries)


def _resolve_executable(name: str, env: dict) -> str:
    """Resolve executable path."""
    if os.path.isabs(name) or os.sep in name or (os.altsep and os.altsep in name):
        return name
    path_key = next((k for k in env if k.upper() == "PATH"), "PATH")
    path_val = env.get(path_key)
    if resolved := shutil.which(name, path=path_val):
        if os.name == "nt":
            suffix = Path(resolved).suffix.lower()
            if not suffix:
                resolved_dir = str(Path(resolved).parent)
                for ext in (".cmd", ".bat", ".exe", ".com"):
                    candidate = Path(resolved_dir) / f"{name}{ext}"
                    if candidate.is_file():
                        return str(candidate)
        return resolved
    if os.name == "nt":
        for base in _get_windows_npm_paths():
            for ext in (".cmd", ".bat", ".exe", ".com"):
                candidate = base / f"{name}{ext}"
                if candidate.is_file():
                    return str(candidate)
    return name


def windows_escape(prompt: str) -> str:
    """Windows style string escaping."""
    result = prompt.replace('\n', '\\n')
    result = result.replace('\r', '\\r')
    result = result.replace('\t', '\\t')
    return result


# ============================================================================
# Shell Command Execution
# ============================================================================

def run_shell_command(cmd: List[str]) -> Generator[str, None, None]:
    """Execute command and stream output line-by-line."""
    env = os.environ.copy()
    _augment_path_env(env)

    popen_cmd = cmd.copy()
    exe_path = _resolve_executable(cmd[0], env)
    popen_cmd[0] = exe_path

    if os.name == "nt" and Path(exe_path).suffix.lower() in {".cmd", ".bat"}:
        def _cmd_quote(arg: str) -> str:
            if not arg:
                return '""'
            arg = arg.replace('%', '%%')
            arg = arg.replace('^', '^^')
            if any(c in arg for c in '&|<>()^" \t'):
                escaped = arg.replace('"', '"^""')
                return f'"{escaped}"'
            return arg
        cmdline = " ".join(_cmd_quote(a) for a in popen_cmd)
        comspec = env.get("COMSPEC", "cmd.exe")
        popen_cmd = f'"{comspec}" /d /s /c "{cmdline}"'

    process = subprocess.Popen(
        popen_cmd,
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding='utf-8',
        errors='replace',
        env=env,
    )

    output_queue: queue.Queue[Optional[str]] = queue.Queue()
    GRACEFUL_SHUTDOWN_DELAY = 0.3

    def is_turn_completed(line: str) -> bool:
        try:
            data = json.loads(line)
            return data.get("type") == "turn.completed"
        except (json.JSONDecodeError, AttributeError, TypeError):
            return False

    def read_output() -> None:
        if process.stdout:
            for line in iter(process.stdout.readline, ""):
                stripped = line.strip()
                output_queue.put(stripped)
                if is_turn_completed(stripped):
                    time.sleep(GRACEFUL_SHUTDOWN_DELAY)
                    process.terminate()
                    break
            process.stdout.close()
        output_queue.put(None)

    thread = threading.Thread(target=read_output)
    thread.start()

    while True:
        try:
            line = output_queue.get(timeout=0.5)
            if line is None:
                break
            yield line
        except queue.Empty:
            if process.poll() is not None and not thread.is_alive():
                break

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    thread.join(timeout=5)

    while not output_queue.empty():
        try:
            line = output_queue.get_nowait()
            if line is not None:
                yield line
        except queue.Empty:
            break


# ============================================================================
# Review Verdict Parsing
# ============================================================================

def parse_verdict_from_review(review_text: str) -> Dict[str, Any]:
    """
    Parse structured verdict from Codex review response.
    Looks for JSON block or verdict markers in the response.
    """
    # Try to find JSON block with verdict
    json_patterns = [
        r'```json\s*(\{[^`]+\})\s*```',
        r'```\s*(\{[^`]+\})\s*```',
        r'(\{["\']verdict["\'][^}]+\})',
    ]

    for pattern in json_patterns:
        match = re.search(pattern, review_text, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                verdict_data = json.loads(match.group(1))
                if "verdict" in verdict_data or "passed" in verdict_data:
                    return {
                        "parsed": True,
                        "passed": verdict_data.get("passed", verdict_data.get("verdict", "").lower() == "pass"),
                        "issues": verdict_data.get("issues", []),
                        "summary": verdict_data.get("summary", ""),
                        "suggestions": verdict_data.get("suggestions", []),
                    }
            except json.JSONDecodeError:
                continue

    # Fallback: look for verdict markers in text
    review_lower = review_text.lower()

    # Strong pass indicators
    pass_indicators = [
        "verdict: pass", "verdict:pass", '"verdict": "pass"',
        "lgtm", "looks good to me", "approved",
        "no critical issues", "no major issues", "no blocking issues",
        "ready for merge", "ready to merge",
    ]

    # Strong fail indicators
    fail_indicators = [
        "verdict: fail", "verdict:fail", '"verdict": "fail"',
        "critical issue", "major issue", "blocking issue",
        "must fix", "needs fixing", "requires changes",
        "security vulnerability", "bug found", "error found",
    ]

    pass_score = sum(1 for indicator in pass_indicators if indicator in review_lower)
    fail_score = sum(1 for indicator in fail_indicators if indicator in review_lower)

    # Extract issues (lines starting with - or * that mention problems)
    issue_patterns = [
        r'[-*]\s*(?:issue|problem|bug|error|warning|concern):\s*(.+)',
        r'[-*]\s*(.+(?:issue|problem|bug|error|should|must|need).+)',
    ]
    issues = []
    for pattern in issue_patterns:
        issues.extend(re.findall(pattern, review_text, re.IGNORECASE | re.MULTILINE))

    return {
        "parsed": False,
        "passed": pass_score > fail_score and fail_score == 0,
        "pass_score": pass_score,
        "fail_score": fail_score,
        "issues": issues[:10],  # Limit to 10 issues
        "summary": "Verdict inferred from review text analysis",
        "suggestions": [],
    }


# ============================================================================
# Logging
# ============================================================================

def setup_logging(log_dir: Path) -> Path:
    """Setup logging directory and return log file path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return log_dir / f"review_{timestamp}.json"


def write_log(log_file: Path, log_data: Dict[str, Any]) -> None:
    """Write review log to file."""
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False, default=str)


# ============================================================================
# Review Prompt Template
# ============================================================================

REVIEW_PROMPT_TEMPLATE = """You are a senior code reviewer. Review the following code/changes and provide a structured assessment.

## Context
{context}

## Code/Changes to Review
{code}

## Review Requirements
1. Check for bugs, logic errors, and edge cases
2. Evaluate code quality and maintainability
3. Identify security vulnerabilities
4. Assess performance implications
5. Verify adherence to best practices

## Response Format
Provide your review in the following JSON format:

```json
{{
  "verdict": "PASS" or "FAIL",
  "passed": true or false,
  "summary": "Brief overall assessment",
  "issues": [
    {{"severity": "critical|major|minor", "description": "Issue description", "location": "file:line if applicable"}}
  ],
  "suggestions": [
    "Improvement suggestion 1",
    "Improvement suggestion 2"
  ]
}}
```

IMPORTANT:
- verdict should be "FAIL" if there are ANY critical or major issues
- verdict should be "PASS" only if there are no critical/major issues (minor issues are acceptable)
- Be thorough but fair in your assessment
"""


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Codex Review Gate - Request code review from Codex CLI"
    )
    parser.add_argument(
        "--context",
        required=True,
        help="Context about what was done (task description, changes made)"
    )
    parser.add_argument(
        "--code",
        required=True,
        help="Code or diff to review (can be file path or inline code)"
    )
    parser.add_argument(
        "--cd",
        required=True,
        help="Project root directory"
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("CODEX_MODEL", ""),
        help="Model to use (e.g., gpt-5, gpt-5.2). Env: CODEX_MODEL"
    )
    parser.add_argument(
        "--reasoning-effort",
        default=os.environ.get("CODEX_REASONING_EFFORT", "high"),
        choices=["none", "low", "medium", "high", "xhigh"],
        help="Reasoning effort level. Env: CODEX_REASONING_EFFORT (default: high)"
    )
    parser.add_argument(
        "--log-dir",
        default="",
        help="Directory for review logs (default: ./codex-review-logs)"
    )
    parser.add_argument(
        "--session-id",
        default="",
        help="Resume previous review session"
    )
    parser.add_argument(
        "--return-all-messages",
        action="store_true",
        help="Include full reasoning trace in output"
    )

    args = parser.parse_args()

    # Prepare code content - resolve path relative to --cd if not absolute
    code_content = args.code
    code_path = Path(args.code)
    if not code_path.is_absolute():
        code_path = Path(args.cd) / code_path
    if code_path.is_file():
        with open(code_path, 'r', encoding='utf-8') as f:
            code_content = f.read()
    elif os.path.isfile(args.code):
        # Fallback: try original path as-is
        with open(args.code, 'r', encoding='utf-8') as f:
            code_content = f.read()

    # Build review prompt
    review_prompt = REVIEW_PROMPT_TEMPLATE.format(
        context=args.context,
        code=code_content
    )

    if os.name == "nt":
        review_prompt = windows_escape(review_prompt)

    # Build Codex command
    # Using read-only sandbox for safe automation (no --full-auto to avoid sandbox override)
    cmd = [
        "codex", "exec",
        "--sandbox", "read-only",
        "--cd", args.cd,
        "--json",
        "--skip-git-repo-check",
    ]

    if args.model:
        cmd.extend(["--model", args.model])

    cmd.extend(["-c", f'model_reasoning_effort="{args.reasoning_effort}"'])

    if args.session_id:
        cmd.extend(["resume", args.session_id])

    cmd.extend(["--", review_prompt])

    # Setup logging
    log_dir = Path(args.log_dir) if args.log_dir else Path(args.cd) / "codex-review-logs"
    log_file = setup_logging(log_dir)

    # Execute review
    all_messages = [] if args.return_all_messages else None
    agent_messages = ""
    success = True
    err_message = ""
    thread_id = None
    start_time = datetime.now()

    for line in run_shell_command(cmd):
        try:
            line_dict = json.loads(line.strip())
            if all_messages is not None:
                all_messages.append(line_dict)

            item = line_dict.get("item", {})
            item_type = item.get("type", "")

            if item_type == "agent_message":
                agent_messages += item.get("text", "")

            if line_dict.get("thread_id"):
                thread_id = line_dict.get("thread_id")

            if "fail" in line_dict.get("type", ""):
                if not agent_messages:
                    success = False
                err_message += f"\n[codex error] {line_dict.get('error', {}).get('message', '')}"

            if "error" in line_dict.get("type", ""):
                error_msg = line_dict.get("message", "")
                is_reconnecting = bool(re.match(r'^Reconnecting\.\.\.\s+\d+/\d+$', error_msg))
                if not is_reconnecting:
                    if not agent_messages:
                        success = False
                    err_message += f"\n[codex error] {error_msg}"

        except json.JSONDecodeError:
            err_message += f"\n[json decode error] {line}"
        except Exception as error:
            err_message += f"\n[unexpected error] {error}"
            success = False
            break

    end_time = datetime.now()

    # Parse verdict from review
    verdict = parse_verdict_from_review(agent_messages) if agent_messages else {
        "parsed": False,
        "passed": False,
        "issues": ["No review response received"],
        "summary": "Review failed - no response from Codex",
        "suggestions": [],
    }

    # Prepare result
    result = {
        "success": success and bool(agent_messages),
        "passed": verdict["passed"],
        "verdict": "PASS" if verdict["passed"] else "FAIL",
        "session_id": thread_id,
        "review": agent_messages,
        "issues": verdict.get("issues", []),
        "summary": verdict.get("summary", ""),
        "suggestions": verdict.get("suggestions", []),
        "verdict_parsed": verdict.get("parsed", False),
    }

    if not success or not agent_messages:
        result["error"] = err_message or "No response received from Codex"
        result["passed"] = False
        result["verdict"] = "FAIL"

    if args.return_all_messages:
        result["all_messages"] = all_messages

    # Write log
    log_data = {
        "timestamp": start_time.isoformat(),
        "duration_seconds": (end_time - start_time).total_seconds(),
        "context": args.context,
        "code_reviewed": code_content[:1000] + "..." if len(code_content) > 1000 else code_content,
        "model": args.model or "default",
        "reasoning_effort": args.reasoning_effort,
        "result": result,
    }
    write_log(log_file, log_data)
    result["log_file"] = str(log_file)

    # Output result
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Exit with appropriate code
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
