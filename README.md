# agentlens

Audit logging for Claude AI agents. Transparent, append-only, OSS.

## Why

Anthropic logs API calls for their own safety monitoring — but that log is not yours.
When your Claude-powered agent takes an action, you need your own tamper-evident record:
for compliance, incident response, and accountability.

**agentlens** is a drop-in wrapper around the Anthropic SDK that captures every `tool_use` and `tool_result` event — without modifying requests or responses.

## Design principles

- **Read-only interception** — requests and responses are never altered
- **Append-only writes** — log entries cannot be edited after creation
- **No AI in the logger** — capture logic is deterministic code, not an LLM
- **Your data stays local** — FileWriter (default) writes to your own machine; no data leaves your environment

## Install

```bash
pip install agentlens-io
```

## Usage

```python
from agentlens import AuditedAnthropic

# Drop-in replacement for anthropic.Anthropic()
client = AuditedAnthropic(log_path="./audit.jsonl")

response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    tools=[...],
    messages=[{"role": "user", "content": "..."}],
)
# Every tool_use and tool_result is now in audit.jsonl
```

## Log format (JSONL)

```json
{"event_type": "tool_use", "tool_use_id": "toolu_01xxx", "tool_name": "bash", "tool_input": {"command": "ls -la"}, "model": "claude-opus-4-6", "timestamp": "2026-04-05T10:00:00+00:00", "session_id": "..."}
{"event_type": "tool_result", "tool_use_id": "toolu_01xxx", "result_content": "file1.txt\nfile2.txt", "is_error": false, "timestamp": "2026-04-05T10:00:01+00:00", "session_id": "..."}
```

## Custom writer

```python
from agentlens.writers import BaseWriter

class MyWriter(BaseWriter):
    def write(self, event) -> None:
        # send to your own DB, S3, SIEM, etc.
        my_db.insert(event.to_json())

client = AuditedAnthropic(writer=MyWriter())
```

## Run tests

```bash
pip install -e ".[dev]"
pytest tests/
```

## License

MIT
