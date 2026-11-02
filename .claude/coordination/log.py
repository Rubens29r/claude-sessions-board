"""PostToolUse hook: records every tool call of every Claude Code session in activity.jsonl (one JSON line per call).

Read by brief.py, which shows each session what the others are doing. Must never block or crash: every error is
swallowed (exit 0).
"""
import json
import os
import sys
import time
from pathlib import Path

DATA_DIR = Path(os.environ.get("CLAUDE_BOARD_DIR") or Path(__file__).resolve().parent)
ACTIVITY = DATA_DIR / "activity.jsonl"
MAX_SIZE = 2_000_000


def summarize(tool_input):
    e = tool_input if isinstance(tool_input, dict) else {}
    for key in ("description", "command", "file_path", "path", "pattern", "url", "prompt", "query"):
        v = e.get(key)
        if isinstance(v, str) and v.strip():
            return f"{key}: {' '.join(v.split())[:160]}"
    return ""


def main():
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")   # Claude Code sends UTF-8
        line = {
            "t": time.strftime("%Y-%m-%d %H:%M:%S"),
            "s": d.get("session_id", "?"),
            "tool": d.get("tool_name", "?"),
            "what": summarize(d.get("tool_input")),
        }
        if ACTIVITY.exists() and ACTIVITY.stat().st_size > MAX_SIZE:
            ACTIVITY.replace(ACTIVITY.with_suffix(".jsonl.1"))
        with open(ACTIVITY, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
