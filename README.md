# codex-chat-export

A GitHub-ready Codex Skill for exporting local Codex Desktop conversations into clean Markdown or JSON.

## What it does

- Lists local Codex conversations from `~/.codex/state_5.sqlite`
- Exports transcript content from `~/.codex/sessions/**/rollout-*.jsonl`
- Supports Markdown and JSON output
- Optionally includes tool calls and tool outputs
- Works well for backups, audits, publishing, or migrating useful threads

## Install as a skill

Clone or copy this folder into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -R codex-chat-export ~/.codex/skills/
```

Then invoke it in Codex with `$codex-chat-export`.

## CLI usage

```bash
python3 scripts/export_codex_chat.py list
python3 scripts/export_codex_chat.py export --latest --format markdown
python3 scripts/export_codex_chat.py export --contains 导出 --format json --output exports/
python3 scripts/export_codex_chat.py export --id <thread-id> --include-tools --output thread.md
```

## Test

```bash
python3 -m unittest discover -s tests -v
```
