"""UserPromptSubmit / SessionStart hook: gives each Claude Code session the state of the OTHER sessions, to the minute.

- their row of the board (board.json: name, task, heavy job running, shared files being written);
- their last actions, taken from activity.jsonl (written by log.py on every tool call).
The text is injected into the session's context (additionalContext). Never crashes.
Your own rules can replace the default ones: put them in rules.txt next to this file.
"""
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(os.environ.get("CLAUDE_BOARD_DIR") or Path(__file__).resolve().parent)
ACTIVITY = DATA_DIR / "activity.jsonl"
BOARD = DATA_DIR / "board.json"
RULES_FILE = DATA_DIR / "rules.txt"
WINDOW_MIN = 20       # recent activity taken into account (minutes)
LAST_N = 4            # actions shown per session
DEFAULT_RULES = ("Rules: one heavy job (CPU/GPU) at a time when possible; never write a file another session lists as "
                 "being written; declare yourself and keep your row up to date with python .claude/coordination/board.py "
                 "<your session> --name ... --task ... [--heavy ...] (not from a sub-agent).")


def read_tail(path, n=600):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 200_000))
            lines = f.read().decode("utf-8", errors="replace").splitlines()[-n:]
        return [json.loads(l) for l in lines if l.strip().startswith("{")]
    except Exception:
        return []


def main():
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")   # Claude Code sends UTF-8
    except Exception:
        d = {}
    me = d.get("session_id", "?")
    event = d.get("hook_event_name", "UserPromptSubmit")
    try:
        board = json.loads(BOARD.read_text(encoding="utf-8"))
    except Exception:
        board = {}
    now = time.time()
    by_session = defaultdict(list)
    for x in read_tail(ACTIVITY):
        try:
            t = time.mktime(time.strptime(x["t"], "%Y-%m-%d %H:%M:%S"))
        except Exception:
            continue
        if x.get("s") != me and now - t <= WINDOW_MIN * 60:
            by_session[x["s"]].append(x)
    others = set(by_session) | {s for s in board if s != me}
    lines = [f"[Session board {time.strftime('%H:%M:%S')}] Your session: {me}"
             f" - your row: {json.dumps(board.get(me, 'not declared'), ensure_ascii=False)}"]
    if not others:
        lines.append("No other session active in the last minutes.")
    for s in sorted(others):
        info = board.get(s, {})
        act = by_session.get(s, [])
        head = f"- Session \"{info.get('name', 'not declared')}\" ({s[:8]})"
        if info.get("task"):
            head += f" - task: {info['task']}"
        if info.get("heavy"):
            head += f" - HEAVY JOB RUNNING: {info['heavy']}"
        if info.get("files"):
            head += f" - writing shared files: {info['files']}"
        if info.get("sub_agent"):
            head += f" - sub-agent: {info['sub_agent']}"
        head += f" - last action at {act[-1]['t'][11:]}" if act else f" - no action for {WINDOW_MIN} min"
        lines.append(head)
        for x in act[-LAST_N:]:
            lines.append(f"    {x['t'][11:]} {x.get('tool')} {x.get('what', '')}")
    try:
        lines.append(RULES_FILE.read_text(encoding="utf-8").strip() if RULES_FILE.exists() else DEFAULT_RULES)
    except Exception:
        lines.append(DEFAULT_RULES)
    # Pure-ASCII JSON: no encoding trouble with the Windows console (accents travel as \u escapes)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": "\n".join(lines)}},
                     ensure_ascii=True))


if __name__ == "__main__":
    main()
