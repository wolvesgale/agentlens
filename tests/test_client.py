"""Unit tests — no real API calls needed."""
import json
import pytest
from unittest.mock import MagicMock, patch
from agentlens import AuditedAnthropic
from agentlens.writers.base import BaseWriter
from agentlens.models import ToolUseEvent, ToolResultEvent


class MemoryWriter(BaseWriter):
    """Captures events in memory for assertions."""
    def __init__(self):
        self.events = []

    def write(self, event) -> None:
        self.events.append(event)


def make_tool_use_block(name="bash", input=None, id="toolu_test01"):
    block = MagicMock()
    block.type = "tool_use"
    block.id = id
    block.name = name
    block.input = input or {"command": "echo hello"}
    return block


def make_response(blocks, model="claude-opus-4-6"):
    resp = MagicMock()
    resp.content = blocks
    resp.model = model
    return resp


@patch("agentlens.client.anthropic.Anthropic")
def test_tool_use_is_logged(mock_anthropic_cls):
    writer = MemoryWriter()
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = make_response([
        make_tool_use_block(name="bash", input={"command": "ls -la"})
    ])

    client = AuditedAnthropic(writer=writer, session_id="test-session")
    client.messages.create(
        model="claude-opus-4-6",
        max_tokens=100,
        messages=[{"role": "user", "content": "List files"}],
    )

    assert len(writer.events) == 1
    event = writer.events[0]
    assert isinstance(event, ToolUseEvent)
    assert event.tool_name == "bash"
    assert event.tool_input == {"command": "ls -la"}
    assert event.session_id == "test-session"


@patch("agentlens.client.anthropic.Anthropic")
def test_tool_result_is_logged(mock_anthropic_cls):
    writer = MemoryWriter()
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = make_response([])

    client = AuditedAnthropic(writer=writer, session_id="test-session")
    client.messages.create(
        model="claude-opus-4-6",
        max_tokens=100,
        messages=[
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_xyz", "content": "file1.txt", "is_error": False}
            ]}
        ],
    )

    assert len(writer.events) == 1
    event = writer.events[0]
    assert isinstance(event, ToolResultEvent)
    assert event.tool_use_id == "toolu_xyz"
    assert event.is_error is False


@patch("agentlens.client.anthropic.Anthropic")
def test_response_is_not_modified(mock_anthropic_cls):
    writer = MemoryWriter()
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    original_response = make_response([make_tool_use_block()])
    mock_client.messages.create.return_value = original_response

    client = AuditedAnthropic(writer=writer)
    result = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=100,
        messages=[{"role": "user", "content": "hi"}],
    )

    assert result is original_response
