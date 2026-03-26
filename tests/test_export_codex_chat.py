from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export_codex_chat.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )


def create_threads_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE threads (
          id TEXT PRIMARY KEY,
          rollout_path TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL,
          source TEXT NOT NULL,
          model_provider TEXT NOT NULL,
          cwd TEXT NOT NULL,
          title TEXT NOT NULL,
          sandbox_policy TEXT NOT NULL DEFAULT '',
          approval_mode TEXT NOT NULL DEFAULT '',
          tokens_used INTEGER NOT NULL DEFAULT 0,
          has_user_event INTEGER NOT NULL DEFAULT 0,
          archived INTEGER NOT NULL DEFAULT 0,
          archived_at INTEGER,
          git_sha TEXT,
          git_branch TEXT,
          git_origin_url TEXT,
          cli_version TEXT NOT NULL DEFAULT '',
          first_user_message TEXT NOT NULL DEFAULT '',
          agent_nickname TEXT,
          agent_role TEXT,
          memory_mode TEXT NOT NULL DEFAULT 'enabled',
          model TEXT,
          reasoning_effort TEXT,
          agent_path TEXT
        )
        """
    )
    return conn


class ExportCodexChatTests(unittest.TestCase):
    def test_list_json_uses_local_fixture_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            codex_home = tmp_path / ".codex"
            sessions_dir = codex_home / "sessions" / "2026" / "03" / "27"
            sessions_dir.mkdir(parents=True)
            rollout_path = sessions_dir / "rollout-2026-03-27T00-00-00-thread-1.jsonl"
            rollout_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "timestamp": "2026-03-26T16:00:00.000Z",
                                "type": "session_meta",
                                "payload": {
                                    "id": "thread-1",
                                    "cwd": "/tmp/project",
                                    "source": "desktop",
                                    "model_provider": "cliproxyapi",
                                    "model": "gpt-5.4",
                                },
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-03-26T16:00:01.000Z",
                                "type": "response_item",
                                "payload": {
                                    "type": "message",
                                    "role": "user",
                                    "content": [{"type": "input_text", "text": "hello"}],
                                },
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            conn = create_threads_db(codex_home / "state_5.sqlite")
            conn.execute(
                """
                INSERT INTO threads (
                  id, rollout_path, created_at, updated_at, source, model_provider, cwd, title, first_user_message, model, reasoning_effort, archived
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "thread-1",
                    str(rollout_path),
                    1774540000,
                    1774540100,
                    "desktop",
                    "cliproxyapi",
                    "/tmp/project",
                    "Sample thread",
                    "hello",
                    "gpt-5.4",
                    "medium",
                    0,
                ),
            )
            conn.commit()
            conn.close()

            result = run("--codex-home", str(codex_home), "list", "--json")
            data = json.loads(result.stdout)
            self.assertEqual(data[0]["id"], "thread-1")
            self.assertEqual(data[0]["title"], "Sample thread")

    def test_export_markdown_includes_messages_and_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            codex_home = tmp_path / ".codex"
            sessions_dir = codex_home / "sessions" / "2026" / "03" / "27"
            sessions_dir.mkdir(parents=True)
            rollout_path = sessions_dir / "rollout-thread-2.jsonl"
            rollout_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "timestamp": "2026-03-26T16:00:00.000Z",
                                "type": "session_meta",
                                "payload": {"id": "thread-2", "cwd": "/tmp/project", "model": "gpt-5.4"},
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-03-26T16:00:01.000Z",
                                "type": "response_item",
                                "payload": {
                                    "type": "message",
                                    "role": "user",
                                    "content": [{"type": "input_text", "text": "导出这个对话"}],
                                },
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-03-26T16:00:02.000Z",
                                "type": "response_item",
                                "payload": {
                                    "type": "function_call",
                                    "name": "exec_command",
                                    "call_id": "call_1",
                                    "arguments": "{\"cmd\":\"pwd\"}",
                                },
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-03-26T16:00:03.000Z",
                                "type": "response_item",
                                "payload": {
                                    "type": "function_call_output",
                                    "call_id": "call_1",
                                    "output": "Output: /tmp/project",
                                },
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-03-26T16:00:04.000Z",
                                "type": "response_item",
                                "payload": {
                                    "type": "message",
                                    "role": "assistant",
                                    "phase": "final",
                                    "content": [{"type": "output_text", "text": "已经导出好了。"}],
                                },
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            conn = create_threads_db(codex_home / "state_5.sqlite")
            conn.execute(
                """
                INSERT INTO threads (
                  id, rollout_path, created_at, updated_at, source, model_provider, cwd, title, first_user_message, model, reasoning_effort, archived
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "thread-2",
                    str(rollout_path),
                    1774540000,
                    1774540100,
                    "desktop",
                    "cliproxyapi",
                    "/tmp/project",
                    "导出测试",
                    "导出这个对话",
                    "gpt-5.4",
                    "medium",
                    0,
                ),
            )
            conn.commit()
            conn.close()

            result = run(
                "--codex-home",
                str(codex_home),
                "export",
                "--id",
                "thread-2",
                "--format",
                "markdown",
                "--include-tools",
            )
            self.assertIn("导出测试", result.stdout)
            self.assertIn("tool call `exec_command`", result.stdout)
            self.assertIn("已经导出好了。", result.stdout)

    def test_export_strips_environment_context_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            codex_home = tmp_path / ".codex"
            sessions_dir = codex_home / "sessions" / "2026" / "03" / "27"
            sessions_dir.mkdir(parents=True)
            rollout_path = sessions_dir / "rollout-thread-3.jsonl"
            rollout_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "timestamp": "2026-03-26T16:00:00.000Z",
                                "type": "session_meta",
                                "payload": {"id": "thread-3", "cwd": "/tmp/project", "model": "gpt-5.4"},
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-03-26T16:00:01.000Z",
                                "type": "response_item",
                                "payload": {
                                    "type": "message",
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "input_text",
                                            "text": "<environment_context>\n  <cwd>/tmp/project</cwd>\n</environment_context>\n\nhello",
                                        }
                                    ],
                                },
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            conn = create_threads_db(codex_home / "state_5.sqlite")
            conn.execute(
                """
                INSERT INTO threads (
                  id, rollout_path, created_at, updated_at, source, model_provider, cwd, title, first_user_message, model, reasoning_effort, archived
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "thread-3",
                    str(rollout_path),
                    1774540000,
                    1774540100,
                    "desktop",
                    "cliproxyapi",
                    "/tmp/project",
                    "环境过滤测试",
                    "hello",
                    "gpt-5.4",
                    "medium",
                    0,
                ),
            )
            conn.commit()
            conn.close()

            result = run("--codex-home", str(codex_home), "export", "--id", "thread-3")
            self.assertNotIn("<environment_context>", result.stdout)
            self.assertIn("hello", result.stdout)

    def test_batch_export_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            codex_home = tmp_path / ".codex"
            sessions_dir = codex_home / "sessions" / "2026" / "03" / "27"
            sessions_dir.mkdir(parents=True)
            conn = create_threads_db(codex_home / "state_5.sqlite")

            for index in (1, 2):
                rollout_path = sessions_dir / f"rollout-thread-{index}.jsonl"
                rollout_path.write_text(
                    "\n".join(
                        [
                            json.dumps(
                                {
                                    "timestamp": "2026-03-26T16:00:00.000Z",
                                    "type": "session_meta",
                                    "payload": {"id": f"thread-{index}", "cwd": "/tmp/project", "model": "gpt-5.4"},
                                },
                                ensure_ascii=False,
                            ),
                            json.dumps(
                                {
                                    "timestamp": "2026-03-26T16:00:01.000Z",
                                    "type": "response_item",
                                    "payload": {
                                        "type": "message",
                                        "role": "user",
                                        "content": [{"type": "input_text", "text": f"hello {index}"}],
                                    },
                                },
                                ensure_ascii=False,
                            ),
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                conn.execute(
                    """
                    INSERT INTO threads (
                      id, rollout_path, created_at, updated_at, source, model_provider, cwd, title, first_user_message, model, reasoning_effort, archived
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"thread-{index}",
                        str(rollout_path),
                        1774540000 + index,
                        1774540100 + index,
                        "desktop",
                        "cliproxyapi",
                        "/tmp/project",
                        f"thread {index}",
                        f"hello {index}",
                        "gpt-5.4",
                        "medium",
                        0,
                    ),
                )
            conn.commit()
            conn.close()

            output_dir = tmp_path / "exports"
            run("--codex-home", str(codex_home), "export", "--all", "--output", str(output_dir))
            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest), 2)
            self.assertTrue((output_dir / "thread-1-thread-1.md").exists())


if __name__ == "__main__":
    unittest.main()
