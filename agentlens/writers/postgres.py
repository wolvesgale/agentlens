"""
PostgreSQL writer — stores events in Neon (or any Postgres).
Install extra: pip install agentlens[postgres]

Usage:
    from agentlens import AuditedAnthropic
    from agentlens.writers import PostgresWriter

    writer = PostgresWriter(dsn="postgresql://user:pass@host/db?sslmode=require")
    writer.migrate()   # create table on first run
    client = AuditedAnthropic(writer=writer)
"""
import json
from dataclasses import asdict
from typing import Optional

from .base import BaseWriter

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS agentlens_events (
    id            BIGSERIAL PRIMARY KEY,
    event_type    TEXT        NOT NULL,
    tool_use_id   TEXT        NOT NULL,
    tool_name     TEXT,
    tool_input    JSONB,
    result_content JSONB,
    is_error      BOOLEAN,
    model         TEXT,
    violations    JSONB       NOT NULL DEFAULT '[]',
    session_id    TEXT,
    ts            TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS agentlens_session_idx
    ON agentlens_events (session_id);
CREATE INDEX IF NOT EXISTS agentlens_ts_idx
    ON agentlens_events (ts DESC);
CREATE INDEX IF NOT EXISTS agentlens_violations_idx
    ON agentlens_events USING GIN (violations)
    WHERE violations != '[]'::jsonb;
"""

_INSERT = """
INSERT INTO agentlens_events
    (event_type, tool_use_id, tool_name, tool_input,
     result_content, is_error, model, violations, session_id, ts)
VALUES
    (%(event_type)s, %(tool_use_id)s, %(tool_name)s, %(tool_input)s,
     %(result_content)s, %(is_error)s, %(model)s, %(violations)s,
     %(session_id)s, %(ts)s)
"""


class PostgresWriter(BaseWriter):
    """Append-only writer to a PostgreSQL table.

    - One row per event (tool_use or tool_result)
    - Violations stored as JSONB → queryable without scanning logs
    - Neon-compatible: pass sslmode=require in the DSN
    """

    def __init__(self, dsn: str):
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            raise ImportError(
                "psycopg2 is required for PostgresWriter. "
                "Install with: pip install agentlens[postgres]"
            )
        self._psycopg2 = psycopg2
        self._extras = psycopg2.extras
        self._dsn = dsn
        self._conn: Optional[object] = None

    def _connection(self):
        if self._conn is None or self._conn.closed:
            self._conn = self._psycopg2.connect(self._dsn)
            self._conn.autocommit = True
        return self._conn

    def migrate(self) -> None:
        """Create table and indexes if they don't exist. Safe to call repeatedly."""
        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
            cur.execute(_CREATE_INDEXES)

    def write(self, event) -> None:
        from ..models import ToolUseEvent, ToolResultEvent

        d = asdict(event)

        if isinstance(event, ToolUseEvent):
            row = {
                "event_type":     "tool_use",
                "tool_use_id":    d["tool_use_id"],
                "tool_name":      d["tool_name"],
                "tool_input":     self._extras.Json(d["tool_input"]),
                "result_content": None,
                "is_error":       None,
                "model":          d["model"],
                "violations":     self._extras.Json(d.get("violations", [])),
                "session_id":     d["session_id"],
                "ts":             d["timestamp"],
            }
        elif isinstance(event, ToolResultEvent):
            content = d["result_content"]
            row = {
                "event_type":     "tool_result",
                "tool_use_id":    d["tool_use_id"],
                "tool_name":      None,
                "tool_input":     None,
                "result_content": self._extras.Json(content) if content is not None else None,
                "is_error":       d["is_error"],
                "model":          None,
                "violations":     self._extras.Json([]),
                "session_id":     d["session_id"],
                "ts":             d["timestamp"],
            }
        else:
            return

        conn = self._connection()
        with conn.cursor() as cur:
            cur.execute(_INSERT, row)

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
