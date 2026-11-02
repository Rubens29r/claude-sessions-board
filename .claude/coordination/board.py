"""Shared task board for several Claude Code sessions working in the same project (board.json).

Each session declares itself and keeps its row up to date:
  python .claude/coordination/board.py <session_id> --name "voice lab" --task "lip-sync test, 14 s clip"
  python .claude/coordination/board.py <session_id> --heavy "GPU render until 21:15"   # long CPU/GPU job running
  python .claude/coordination/board.py <session_id> --free                             # long job finished
  python .claude/coordination/board.py <session_id> --files "docs/STATE.md"            # shared files being written
  python .claude/coordination/board.py <session_id> --end                              # the session leaves
  python .claude/coordination/board.py --show                                          # the whole board
The session_id of a session is shown to it on every message by the brief.py hook.

Sub-agents share their parent's session_id: they should not declare themselves. If one does anyway with another
--name, its line goes into the "sub_agent" field instead of overwriting the parent's row, and its --end only clears that
field (the parent runs --end again to leave). To rename a session on purpose: --rename.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

DATA_DIR = Path(os.environ.get("CLAUDE_BOARD_DIR") or Path(__file__).resolve().parent)
BOARD = DATA_DIR / "board.json"


def read_board():
    try:
        return json.loads(BOARD.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_board(d):
    # Write-then-rename: two sessions writing at the same instant never leave a half-written board.
    tmp = BOARD.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(BOARD)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("session", nargs="?")
    ap.add_argument("--name")
    ap.add_argument("--task")
    ap.add_argument("--heavy")
    ap.add_argument("--files")
    # --free: heavy job finished, with no argument (PowerShell drops an empty "" argument)
    ap.add_argument("--free", action="store_true")
    ap.add_argument("--rename", action="store_true")
    ap.add_argument("--end", action="store_true")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    d = read_board()
    if a.show or not a.session:
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return
    if a.end:
        e = d.get(a.session, {})
        if e.get("sub_agent"):
            # most likely a sub-agent leaving: the parent stays (run --end again to remove it)
            e.pop("sub_agent")
        else:
            d.pop(a.session, None)
    else:
        e = d.setdefault(a.session, {})
        if a.name and e.get("name") and a.name != e["name"] and not a.rename:
            # a sub-agent declaring itself: the parent's row stays intact
            e["sub_agent"] = f"{a.name} : {a.task or ''}".strip(" :")
            e["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            write_board(d)
            print(json.dumps(e, ensure_ascii=False))
            return
        if a.free:
            a.heavy = ""
        for key in ("name", "task", "heavy", "files"):
            v = getattr(a, key)
            if v is not None:
                e[key] = v.strip()
        e["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    write_board(d)
    print(json.dumps(d.get(a.session, {"removed": a.session}), ensure_ascii=False))


if __name__ == "__main__":
    main()
