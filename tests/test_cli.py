"""tests/test_cli.py — CLIビューアのテスト"""
import json
import sys
from io import StringIO
from pathlib import Path

import pytest

from agentlens.cli import cmd_view, cmd_summary, main


EVENTS = [
    {
        "event_type": "tool_use",
        "tool_name": "bash",
        "tool_input": {"command": "ls -la"},
        "session_id": "sess-001",
        "timestamp": "2026-04-06T10:00:00",
        "violations": [],
    },
    {
        "event_type": "tool_result",
        "result_content": [{"type": "text", "text": "total 0"}],
        "is_error": False,
        "tool_use_id": "tu_abc",
        "session_id": "sess-001",
        "timestamp": "2026-04-06T10:00:01",
        "violations": [],
    },
    {
        "event_type": "tool_use",
        "tool_name": "bash",
        "tool_input": {"command": "rm -rf /"},
        "session_id": "sess-001",
        "timestamp": "2026-04-06T10:00:02",
        "violations": [
            {
                "rule_id": "SHELL_RM_ROOT",
                "severity": "critical",
                "description": "危険なコマンド",
                "matched_value": "rm -rf /",
            }
        ],
    },
]


@pytest.fixture
def audit_file(tmp_path: Path) -> Path:
    p = tmp_path / "audit.jsonl"
    with open(p, "w") as f:
        for ev in EVENTS:
            f.write(json.dumps(ev) + "\n")
    return p


def _capture(func, *args, **kwargs) -> str:
    buf = StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        func(*args, **kwargs)
    finally:
        sys.stdout = old
    return buf.getvalue()


def test_view_shows_all_events(audit_file):
    out = _capture(cmd_view, audit_file, session=None, violations_only=False)
    assert "TOOL USE" in out
    assert "TOOL RESULT" in out
    assert "bash" in out
    assert "ls -la" in out


def test_view_shows_violations(audit_file):
    out = _capture(cmd_view, audit_file, session=None, violations_only=False)
    assert "SHELL_RM_ROOT" in out
    assert "CRITICAL" in out
    assert "rm -rf /" in out


def test_view_violations_only_filters(audit_file):
    out = _capture(cmd_view, audit_file, session=None, violations_only=True)
    assert "SHELL_RM_ROOT" in out
    # 違反なしのイベントは表示されない
    assert "ls -la" not in out


def test_view_session_filter(audit_file):
    out_match   = _capture(cmd_view, audit_file, session="sess-001", violations_only=False)
    out_nomatch = _capture(cmd_view, audit_file, session="sess-999", violations_only=False)
    assert "bash" in out_match
    assert "bash" not in out_nomatch


def test_summary_counts(audit_file):
    out = _capture(cmd_summary, audit_file)
    assert "2" in out   # tool_use: 2件
    assert "1" in out   # sessions: 1件
    assert "SHELL_RM_ROOT" not in out   # summaryには rule_id は出さない
    assert "critical" in out.lower()


def test_view_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        cmd_view(tmp_path / "notexist.jsonl", None, False)


def test_main_view(audit_file):
    out = _capture(main, ["agentlens", "view", str(audit_file)])
    assert "TOOL USE" in out


def test_main_summary(audit_file):
    out = _capture(main, ["agentlens", "summary", str(audit_file)])
    assert "agentlens" in out.lower()


def test_main_no_args():
    with pytest.raises(SystemExit):
        main(["agentlens"])
