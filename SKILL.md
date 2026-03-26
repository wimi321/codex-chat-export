---
name: codex-chat-export
description: Export local Codex Desktop conversations from ~/.codex into Markdown or JSON. Use this skill when the user wants to back up chat history, extract a thread by id or title, batch-export multiple conversations, or turn rollout JSONL sessions into readable transcripts.
---

# Codex Chat Export

## Overview

This skill turns local Codex Desktop conversation data into readable transcript exports. It is built for backup, knowledge capture, publishing, and thread migration workflows.

## When To Use

Use this skill when the user asks to:

- export Codex chat history
- back up one conversation or all conversations
- find a thread by title and save it as Markdown
- convert rollout JSONL files into readable transcripts
- archive useful Codex sessions into JSON for further processing

## Workflow

1. Confirm the target scope.
   Single thread: use `list` first, then `export --id` or `export --contains`.
   Latest thread: use `export --latest`.
   Batch export: use `export --all --output <dir>`.
2. Run the bundled script:
   `python3 scripts/export_codex_chat.py ...`
3. Prefer Markdown for readable archives and JSON for automation pipelines.
4. Add `--include-tools` only when tool traces are useful.
5. For cleaner exports, leave environment stripping on unless the user explicitly wants raw input context.

## Commands

List recent threads:

```bash
codex-chat-export list
```

List as JSON:

```bash
codex-chat-export list --json
```

Export the latest thread as Markdown to stdout:

```bash
codex-chat-export export --latest --format markdown
```

Export a matching thread into a directory:

```bash
codex-chat-export export --contains 复盘 --format markdown --output exports/
```

Export one thread with tool traces:

```bash
codex-chat-export export --id <thread-id> --include-tools --output thread.md
```

## Notes

- Thread discovery uses `~/.codex/state_5.sqlite`.
- Transcript content comes from `~/.codex/sessions/**/rollout-*.jsonl`.
- Encrypted reasoning is intentionally skipped.
- Duplicate telemetry events are skipped to keep exports clean.

Read [references/rollout-format.md](references/rollout-format.md) when you need details about the underlying record types.
