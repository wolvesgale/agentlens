"""Tests for PostgresWriter — no real DB needed."""
import pytest
from unittest.mock import MagicMock, patch, call
from agentlens.models import ToolUseEvent, ToolResultEvent


def _make_mock_conn():
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


def _make_writer(mock_conn):
    """Build a PostgresWriter with psycopg2 fully mocked."""
    import sys
    mock_psycopg2 = MagicMock()
    mock_psycopg2.connect.return_value = mock_conn
    mock_psycopg2.extras.Json = lambda x: x   # passthrough for assertions

    with patch.dict(sys.modules, {"psycopg2": mock_psycopg2, "psycopg2.extras": mock_psycopg2.extras}):
        from agentlens.writers.postgres import PostgresWriter
        writer = PostgresWriter(dsn="postgresql://fake/db")
        writer._conn = mock_conn
        writer._psycopg2 = mock_psycopg2
        writer._extras = mock_psycopg2.extras
        return writer, mock_psycopg2


def test_tool_use_event_is_inserted():
    mock_conn, mock_cursor = _make_mock_conn()
    writer, _ = _make_writer(mock_conn)

    event = ToolUseEvent(
        tool_use_id="toolu_abc",
        tool_name="bash",
        tool_input={"command": "ls"},
        model="claude-opus-4-6",
        session_id="sess-1",
    )
    writer.write(event)

    mock_cursor.execute.assert_called_once()
    sql, params = mock_cursor.execute.call_args[0]
    assert "INSERT INTO agentlens_events" in sql
    assert params["event_type"] == "tool_use"
    assert params["tool_name"] == "bash"
    assert params["session_id"] == "sess-1"
    assert params["result_content"] is None


def test_tool_result_event_is_inserted():
    mock_conn, mock_cursor = _make_mock_conn()
    writer, _ = _make_writer(mock_conn)

    event = ToolResultEvent(
        tool_use_id="toolu_abc",
        result_content="file1.txt",
        is_error=False,
        session_id="sess-1",
    )
    writer.write(event)

    mock_cursor.execute.assert_called_once()
    sql, params = mock_cursor.execute.call_args[0]
    assert params["event_type"] == "tool_result"
    assert params["is_error"] is False
    assert params["tool_name"] is None


def test_migrate_runs_two_create_statements():
    mock_conn, mock_cursor = _make_mock_conn()
    writer, _ = _make_writer(mock_conn)
    writer.migrate()

    assert mock_cursor.execute.call_count == 2
    first_sql = mock_cursor.execute.call_args_list[0][0][0]
    assert "CREATE TABLE IF NOT EXISTS agentlens_events" in first_sql


def test_violations_are_stored():
    mock_conn, mock_cursor = _make_mock_conn()
    writer, _ = _make_writer(mock_conn)

    event = ToolUseEvent(
        tool_use_id="toolu_xyz",
        tool_name="bash",
        tool_input={"command": "rm -rf /"},
        violations=[{"rule_id": "SHELL_RM_ROOT", "severity": "critical"}],
        session_id="sess-2",
    )
    writer.write(event)

    _, params = mock_cursor.execute.call_args[0]
    assert params["violations"] == [{"rule_id": "SHELL_RM_ROOT", "severity": "critical"}]
