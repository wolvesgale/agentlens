"""
Basic example: weather tool with full audit logging.
Run with: python examples/basic.py
Audit log is written to ./audit.jsonl
"""
import os
import json
from agentlens import AuditedAnthropic

client = AuditedAnthropic(log_path="./audit.jsonl")

tools = [
    {
        "name": "get_weather",
        "description": "Get current weather for a location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name, e.g. Tokyo"}
            },
            "required": ["location"],
        },
    }
]

messages = [{"role": "user", "content": "What's the weather in Tokyo?"}]

# Turn 1: Claude decides to call get_weather → logged as tool_use
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    tools=tools,
    messages=messages,
)

print("Turn 1 stop_reason:", response.stop_reason)

# Simulate tool execution
if response.stop_reason == "tool_use":
    tool_block = next(b for b in response.content if b.type == "tool_use")
    print(f"Tool called: {tool_block.name}({tool_block.input})")

    # Turn 2: return tool result → logged as tool_result
    messages += [
        {"role": "assistant", "content": response.content},
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": "Sunny, 22°C",
                }
            ],
        },
    ]

    final = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        tools=tools,
        messages=messages,
    )
    print("Final answer:", final.content[0].text)

# Show what was logged
print("\n--- Audit log ---")
with open("./audit.jsonl") as f:
    for line in f:
        print(json.dumps(json.loads(line), indent=2, ensure_ascii=False))
