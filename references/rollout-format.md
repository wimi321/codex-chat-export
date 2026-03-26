# Codex Rollout Format

This skill exports from `~/.codex/sessions/**/rollout-*.jsonl`, which is the most direct per-thread artifact found on local Codex Desktop installs.

## Records used by the exporter

- `session_meta`: Thread-level metadata such as id, cwd, source, model, and cli version.
- `response_item` with `payload.type=message`: Canonical user and assistant messages.
- `response_item` with `payload.type=function_call`: Tool invocation records.
- `response_item` with `payload.type=function_call_output`: Tool outputs.

## Records intentionally skipped

- `response_item` with `payload.type=reasoning`: Usually encrypted or partial; not safe to rely on for readable export.
- `response_item.message` with roles other than `user` or `assistant`: Internal prompt material rather than visible chat.
- `event_msg` duplicates like `user_message` and `agent_message`: The same visible chat content is already present in `response_item.message`.
- `token_count`: Telemetry noise for transcript exports.

## Why this source is preferred

- It is per-conversation rather than global.
- It is append-only JSONL, so parsing is simple and portable.
- It avoids coupling the skill to unstable internal sqlite schemas more than necessary.

## Thread discovery

The bundled script prefers `~/.codex/state_5.sqlite` to discover thread ids, titles, timestamps, and rollout paths. Export content itself still comes from the rollout JSONL files.
