"""
test_hash_chain.py — ハッシュチェーン整合性テスト (v0.4.0)
"""
import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from agentlens.models import ToolUseEvent, ToolResultEvent
from agentlens.writers.file import FileWriter, _sha256, _GENESIS


# ─────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────

def _write_events(path: Path, n: int = 3) -> list[dict]:
    writer = FileWriter(str(path))
    for i in range(n):
        writer.write(ToolUseEvent(
            tool_use_id=f"id_{i}",
            tool_name="bash",
            tool_input={"command": f"echo {i}"},
            model="claude-haiku-4-5-20251001",
        ))
    entries = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    return entries


def _verify(path: Path) -> bool:
    """Pythonレベルでチェーンを検証。Trueなら整合、Falseなら改ざん検知。"""
    prev = _sha256(_GENESIS)
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        stored = entry.get("entry_hash", "")
        content = json.dumps({k: v for k, v in entry.items() if k != "entry_hash"}, ensure_ascii=False)
        if _sha256(prev + content) != stored:
            return False
        prev = stored
    return True


# ─────────────────────────────────────────────
# テスト
# ─────────────────────────────────────────────

def test_first_entry_has_genesis_based_hash():
    """1件目のhashがgenesisハッシュから計算されていること。"""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    path.unlink()

    writer = FileWriter(str(path))
    ev = ToolUseEvent(tool_name="bash", tool_input={"command": "ls"})
    writer.write(ev)

    entry = json.loads(path.read_text().strip())
    content = json.dumps({k: v for k, v in entry.items() if k != "entry_hash"}, ensure_ascii=False)
    expected = _sha256(_sha256(_GENESIS) + content)
    assert entry["entry_hash"] == expected


def test_consecutive_entries_are_linked():
    """連続するエントリのhashが前エントリのhashを参照していること。"""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    path.unlink()

    entries = _write_events(path, n=3)
    assert len(entries) == 3

    # entry[1].hash は entry[0].hash を使って計算されているはず
    prev_hash = entries[0]["entry_hash"]
    content1  = json.dumps({k: v for k, v in entries[1].items() if k != "entry_hash"}, ensure_ascii=False)
    assert entries[1]["entry_hash"] == _sha256(prev_hash + content1)


def test_verify_passes_on_intact_log():
    """改ざんなしのログはverifyがTrueを返すこと。"""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    path.unlink()

    _write_events(path, n=5)
    assert _verify(path) is True


def test_verify_detects_tampered_entry():
    """中間エントリを書き換えるとverifyがFalseを返すこと。"""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    path.unlink()

    _write_events(path, n=4)

    lines = path.read_text().splitlines()
    # 2行目(index=1)のtool_nameを書き換える
    entry = json.loads(lines[1])
    entry["tool_name"] = "rm"  # 改ざん
    lines[1] = json.dumps(entry, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n")

    assert _verify(path) is False


def test_verify_detects_deleted_entry():
    """中間エントリを削除するとverifyがFalseを返すこと。"""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    path.unlink()

    _write_events(path, n=4)

    lines = path.read_text().splitlines()
    # 2行目を削除（index=1）
    del lines[1]
    path.write_text("\n".join(lines) + "\n")

    assert _verify(path) is False


def test_tool_result_event_also_chained():
    """ToolResultEventもハッシュチェーンに含まれること。"""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    path.unlink()

    writer = FileWriter(str(path))
    writer.write(ToolUseEvent(tool_name="bash", tool_input={"command": "ls"}))
    writer.write(ToolResultEvent(tool_use_id="id_0", result_content="file.txt"))

    assert _verify(path) is True
    entries = [json.loads(l) for l in path.read_text().splitlines()]
    assert entries[1]["entry_hash"] != ""
