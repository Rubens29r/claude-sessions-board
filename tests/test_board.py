"""Two sessions on one board: declare, log, brief, sub-agent, leave. Run: python -m unittest discover tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / ".claude" / "coordination"


class TestBoard(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.env = {**os.environ, "CLAUDE_BOARD_DIR": self.dir.name}

    def tearDown(self):
        self.dir.cleanup()

    def run_script(self, name, *args, stdin=None):
        r = subprocess.run([sys.executable, str(SCRIPTS / name), *args], input=(stdin or "").encode("utf-8"),
                           capture_output=True, env=self.env, check=True)
        return r.stdout.decode("utf-8")

    def brief(self, session):
        out = self.run_script("brief.py", stdin=json.dumps({"session_id": session, "hook_event_name": "UserPromptSubmit"}))
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]

    def test_two_sessions(self):
        self.run_script("board.py", "aaaa1111", "--name", "front end", "--task", "login page")
        self.run_script("board.py", "bbbb2222", "--name", "renders", "--task", "video export", "--heavy", "GPU render",
                        "--files", "docs/STATE.md")
        self.run_script("log.py", stdin=json.dumps({"session_id": "bbbb2222", "tool_name": "Bash",
                                                    "tool_input": {"description": "Render the intro"}}))
        seen_by_a = self.brief("aaaa1111")
        self.assertIn('Session "renders" (bbbb2222)', seen_by_a)
        self.assertIn("HEAVY JOB RUNNING: GPU render", seen_by_a)
        self.assertIn("writing shared files: docs/STATE.md", seen_by_a)
        self.assertIn("Bash description: Render the intro", seen_by_a)
        self.assertNotIn('Session "front end"', seen_by_a)  # a session never sees itself among the others

        # A sub-agent shares its parent's id: it must not overwrite the parent's row.
        self.run_script("board.py", "bbbb2222", "--name", "helper", "--task", "check frames")
        row = json.loads(self.run_script("board.py", "--show"))["bbbb2222"]
        self.assertEqual(row["name"], "renders")
        self.assertEqual(row["sub_agent"], "helper : check frames")

        self.run_script("board.py", "bbbb2222", "--free")
        self.assertNotIn("HEAVY JOB RUNNING", self.brief("aaaa1111"))
        self.run_script("board.py", "bbbb2222", "--end")  # the sub-agent leaves
        self.run_script("board.py", "bbbb2222", "--end")  # the session leaves
        self.assertNotIn("bbbb2222", json.loads(self.run_script("board.py", "--show")))

    def test_custom_rules(self):
        Path(self.dir.name, "rules.txt").write_text("Rules: only one session touches the database.", encoding="utf-8")
        self.assertTrue(self.brief("aaaa1111").endswith("Rules: only one session touches the database."))


if __name__ == "__main__":
    unittest.main()
