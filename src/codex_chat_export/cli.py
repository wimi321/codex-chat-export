#!/usr/bin/env python3
"""
Export Codex Desktop conversations from local rollout JSONL files.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CODEX_HOME = Path.home() / ".codex"
STATE_DB_NAME = "state_5.sqlite"
THREAD_QUERY = """
SELECT
  id,
  title,
  first_user_message,
  created_at,
  updated_at,
  rollout_path,
  cwd,
  source,
  model_provider,
  model,
  reasoning_effort,
  archived
FROM threads
ORDER BY updated_at DESC, id DESC
"""


@dataclass
class ThreadRecord:
    id: str
    title: str
    first_user_message: str
    created_at: str | None
    updated_at: str | None
    rollout_path: str
    cwd: str
    source: str
    model_provider: str
    model: str | None
    reasoning_effort: str | None
    archived: bool


def unix_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def truncate_title(value: str, limit: int = 120) -> str:
    title = value.replace("\n", " ").strip()
    if len(title) <= limit:
        return title
    return title[: limit - 3] + "..."


def load_threads_from_sqlite(codex_home: Path) -> list[ThreadRecord]:
    db_path = codex_home / STATE_DB_NAME
    if not db_path.exists():
        return []

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(THREAD_QUERY).fetchall()
    finally:
        conn.close()

    return [
        ThreadRecord(
            id=row["id"],
            title=row["title"] or row["id"],
            first_user_message=row["first_user_message"] or "",
            created_at=unix_to_iso(row["created_at"]),
            updated_at=unix_to_iso(row["updated_at"]),
            rollout_path=row["rollout_path"],
            cwd=row["cwd"] or "",
            source=row["source"] or "",
            model_provider=row["model_provider"] or "",
            model=row["model"],
            reasoning_effort=row["reasoning_effort"],
            archived=bool(row["archived"]),
        )
        for row in rows
        if row["rollout_path"]
    ]


def load_threads_from_rollouts(codex_home: Path) -> list[ThreadRecord]:
    threads: list[ThreadRecord] = []
    for rollout_path in sorted((codex_home / "sessions").glob("**/rollout-*.jsonl"), reverse=True):
        try:
            with rollout_path.open("r", encoding="utf-8") as handle:
                first_line = handle.readline()
        except OSError:
            continue
        if not first_line:
            continue
        try:
            record = json.loads(first_line)
        except json.JSONDecodeError:
            continue
        if record.get("type") != "session_meta":
            continue
        payload = record.get("payload") or {}
        thread_id = payload.get("id")
        if not thread_id:
            continue
        session_timestamp = payload.get("timestamp")
        threads.append(
            ThreadRecord(
                id=thread_id,
                title=thread_id,
                first_user_message="",
                created_at=session_timestamp,
                updated_at=record.get("timestamp") or session_timestamp,
                rollout_path=str(rollout_path),
                cwd=payload.get("cwd", ""),
                source=payload.get("source", ""),
                model_provider=payload.get("model_provider", ""),
                model=payload.get("model"),
                reasoning_effort=payload.get("reasoning_effort"),
                archived=False,
            )
        )
    return threads


def load_threads(codex_home: Path) -> list[ThreadRecord]:
    threads = load_threads_from_sqlite(codex_home)
    return threads if threads else load_threads_from_rollouts(codex_home)


def extract_text_parts(content: list[dict[str, Any]] | None) -> str:
    if not content:
        return ""
    parts: list[str] = []
    for item in content:
        text = item.get("text")
        if text:
            parts.append(text)
    return "".join(parts).rstrip()


def clean_message_text(text: str, strip_environment: bool) -> str:
    if strip_environment:
        text = re.sub(r"^\s*<environment_context>.*?</environment_context>\s*", "", text, flags=re.S)
    return text.rstrip()


def normalize_message(
    message_index: int,
    record: dict[str, Any],
    strip_environment: bool,
) -> dict[str, Any] | None:
    payload = record.get("payload") or {}
    timestamp = record.get("timestamp")

    if record.get("type") != "response_item":
        return None

    payload_type = payload.get("type")
    if payload_type == "message":
        role = payload.get("role", "assistant")
        if role not in {"user", "assistant"}:
            return None
        content = clean_message_text(extract_text_parts(payload.get("content")), strip_environment)
        if not content:
            return None
        return {
            "index": message_index,
            "timestamp": timestamp,
            "kind": "message",
            "role": role,
            "phase": payload.get("phase"),
            "text": content,
        }
    if payload_type == "function_call":
        return {
            "index": message_index,
            "timestamp": timestamp,
            "kind": "tool_call",
            "tool_name": payload.get("name"),
            "call_id": payload.get("call_id"),
            "arguments": payload.get("arguments", ""),
        }
    if payload_type == "function_call_output":
        return {
            "index": message_index,
            "timestamp": timestamp,
            "kind": "tool_result",
            "call_id": payload.get("call_id"),
            "output": payload.get("output", ""),
        }
    return None


def parse_rollout(
    rollout_path: Path,
    include_tools: bool,
    strip_environment: bool,
) -> dict[str, Any]:
    session_meta: dict[str, Any] | None = None
    items: list[dict[str, Any]] = []
    message_index = 1

    with rollout_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("type") == "session_meta":
                session_meta = record.get("payload") or {}
                continue
            item = normalize_message(message_index, record, strip_environment)
            if not item:
                continue
            if not include_tools and item["kind"] in {"tool_call", "tool_result"}:
                continue
            items.append(item)
            message_index += 1

    return {
        "session_meta": session_meta or {},
        "items": items,
    }


def apply_filters(
    threads: list[ThreadRecord],
    *,
    contains: str | None,
    updated_after: str | None,
    include_archived: bool,
) -> list[ThreadRecord]:
    filtered = threads
    if not include_archived:
        filtered = [thread for thread in filtered if not thread.archived]
    if contains:
        needle = contains.casefold()
        filtered = [
            thread
            for thread in filtered
            if needle in thread.title.casefold() or needle in thread.first_user_message.casefold()
        ]
    if updated_after:
        filtered = [
            thread
            for thread in filtered
            if thread.updated_at and thread.updated_at >= updated_after
        ]
    return filtered


def select_threads(
    threads: list[ThreadRecord],
    thread_id: str | None,
    latest: bool,
    contains: str | None,
    export_all: bool,
    updated_after: str | None,
    include_archived: bool,
) -> list[ThreadRecord]:
    filtered = apply_filters(
        threads,
        contains=contains,
        updated_after=updated_after,
        include_archived=include_archived,
    )
    if thread_id:
        return [thread for thread in filtered if thread.id == thread_id]
    if latest:
        return filtered[:1]
    if export_all or contains or updated_after:
        return filtered
    raise SystemExit("Choose one of --id, --contains, --updated-after, --latest, or --all.")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^a-z0-9\-_]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-") or "conversation"


def render_markdown(thread: ThreadRecord, transcript: dict[str, Any]) -> str:
    meta = transcript["session_meta"]
    lines = [
        f"# {thread.title}",
        "",
        f"- Thread ID: `{thread.id}`",
        f"- Created At: `{thread.created_at or 'unknown'}`",
        f"- Updated At: `{thread.updated_at or 'unknown'}`",
        f"- Model: `{thread.model or meta.get('model') or 'unknown'}`",
        f"- Provider: `{thread.model_provider or meta.get('model_provider') or 'unknown'}`",
        f"- Source: `{thread.source or meta.get('source') or 'unknown'}`",
        f"- CWD: `{thread.cwd or meta.get('cwd') or ''}`",
        f"- Rollout: `{thread.rollout_path}`",
        "",
        "## Transcript",
        "",
    ]

    for item in transcript["items"]:
        if item["kind"] == "message":
            title = item["role"]
            if item.get("phase"):
                title += f" ({item['phase']})"
            lines.extend([f"### {item['index']}. {title}", "", item["text"], ""])
        elif item["kind"] == "tool_call":
            lines.extend(
                [
                    f"### {item['index']}. tool call `{item.get('tool_name') or 'unknown'}`",
                    "",
                    "```json",
                    item.get("arguments", "").strip() or "{}",
                    "```",
                    "",
                ]
            )
        elif item["kind"] == "tool_result":
            lines.extend(
                [
                    f"### {item['index']}. tool result `{item.get('call_id') or 'unknown'}`",
                    "",
                    "```text",
                    item.get("output", "").rstrip(),
                    "```",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_output(text: str, output_path: Path | None) -> None:
    if output_path is None:
        sys.stdout.write(text)
        return
    ensure_parent_dir(output_path)
    output_path.write_text(text, encoding="utf-8")


def build_export_payload(thread: ThreadRecord, transcript: dict[str, Any]) -> dict[str, Any]:
    return {
        "thread": asdict(thread),
        "session_meta": transcript["session_meta"],
        "items": transcript["items"],
        "message_count": len([item for item in transcript["items"] if item["kind"] == "message"]),
    }


def resolve_output_path(output: str | None, fmt: str, thread: ThreadRecord, multi: bool) -> Path | None:
    if not output:
        return None
    raw = Path(output).expanduser()
    if multi or raw.is_dir() or output.endswith(os.sep):
        raw.mkdir(parents=True, exist_ok=True)
        suffix = "md" if fmt == "markdown" else "json"
        return raw / f"{thread.id}-{slugify(thread.title)[:80]}.{suffix}"
    return raw


def write_manifest(directory: Path, exports: list[dict[str, Any]]) -> None:
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(json.dumps(exports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command_list(args: argparse.Namespace) -> int:
    threads = apply_filters(
        load_threads(args.codex_home),
        contains=args.contains,
        updated_after=args.updated_after,
        include_archived=args.include_archived,
    )
    if args.limit:
        threads = threads[: args.limit]
    if args.json:
        json.dump([asdict(thread) for thread in threads], sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    for thread in threads:
        updated_at = thread.updated_at or "unknown"
        print(f"{thread.id}\t{updated_at}\t{truncate_title(thread.title)}")
    return 0


def command_export(args: argparse.Namespace) -> int:
    threads = load_threads(args.codex_home)
    selected = select_threads(
        threads,
        args.id,
        args.latest,
        args.contains,
        args.all,
        args.updated_after,
        args.include_archived,
    )
    if not selected:
        raise SystemExit("No matching conversations found.")

    multi = len(selected) > 1
    if multi and not args.output:
        raise SystemExit("Batch export requires --output to point to a directory.")

    manifest_entries: list[dict[str, Any]] = []
    for thread in selected:
        transcript = parse_rollout(
            Path(thread.rollout_path),
            include_tools=args.include_tools,
            strip_environment=not args.keep_environment_context,
        )
        output_path = resolve_output_path(args.output, args.format, thread, multi)
        if args.format == "markdown":
            rendered = render_markdown(thread, transcript)
        else:
            rendered = json.dumps(build_export_payload(thread, transcript), ensure_ascii=False, indent=2) + "\n"
        write_output(rendered, output_path)
        if output_path is not None:
            print(f"wrote {output_path}", file=sys.stderr)
            manifest_entries.append(
                {
                    "thread_id": thread.id,
                    "title": thread.title,
                    "path": str(output_path),
                    "format": args.format,
                }
            )

    if multi and args.output:
        write_manifest(Path(args.output).expanduser(), manifest_entries)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List and export Codex Desktop conversations from local rollout files."
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=DEFAULT_CODEX_HOME,
        help="Path to the Codex home directory. Defaults to ~/.codex",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List available conversations")
    list_parser.add_argument("--limit", type=int, default=20, help="Number of conversations to show")
    list_parser.add_argument("--json", action="store_true", help="Emit JSON instead of tab-separated rows")
    list_parser.add_argument("--contains", help="Filter threads by title or first user message")
    list_parser.add_argument("--updated-after", help="Only include threads updated on or after an ISO timestamp")
    list_parser.add_argument("--include-archived", action="store_true", help="Include archived threads")
    list_parser.set_defaults(func=command_list)

    export_parser = subparsers.add_parser("export", help="Export one or more conversations")
    selector = export_parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--id", help="Thread ID to export")
    selector.add_argument("--contains", help="Export threads whose title or first message contains text")
    selector.add_argument("--updated-after", help="Export threads updated on or after an ISO timestamp")
    selector.add_argument("--latest", action="store_true", help="Export the most recently updated thread")
    selector.add_argument("--all", action="store_true", help="Export all matching threads")
    export_parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")
    export_parser.add_argument("--output", help="Output file path or directory. Prints to stdout when omitted.")
    export_parser.add_argument("--include-tools", action="store_true", help="Include tool call and tool result records")
    export_parser.add_argument(
        "--keep-environment-context",
        action="store_true",
        help="Keep leading <environment_context> blocks in user messages",
    )
    export_parser.add_argument("--include-archived", action="store_true", help="Include archived threads")
    export_parser.set_defaults(func=command_export)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.codex_home = args.codex_home.expanduser()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
