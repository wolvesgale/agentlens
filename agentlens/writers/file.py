import hashlib
import json
from pathlib import Path

from .base import BaseWriter

# 最初のエントリのprev_hashとして使うジェネシス値
_GENESIS = "agentlens_genesis_v0.4.0"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _last_hash(path: Path) -> str:
    """ログファイルの最終エントリのentry_hashを返す。存在しない場合はgenesisハッシュ。"""
    if not path.exists():
        return _sha256(_GENESIS)
    last = ""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                last = line
    if not last:
        return _sha256(_GENESIS)
    try:
        return json.loads(last).get("entry_hash", _sha256(_GENESIS))
    except json.JSONDecodeError:
        return _sha256(_GENESIS)


class FileWriter(BaseWriter):
    """Appends each event as a JSON line to a local file with SHA-256 hash chain.

    - Append-only: never overwrites existing entries
    - Hash chain: entry_hash = SHA256(prev_hash + entry_content_without_hash)
    - Tamper detection: `agentlens verify <file>` recomputes and compares hashes
    - No external dependency: works offline, zero config
    - JSONL format: easy to pipe into jq, grep, or any log tool
    """

    def __init__(self, path: str = "./agentlens_audit.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prev_hash = _last_hash(self.path)

    def write(self, event) -> None:
        content = event.to_json_without_hash()
        event.entry_hash = _sha256(self._prev_hash + content)
        self._prev_hash = event.entry_hash
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")
