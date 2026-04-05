from pathlib import Path
from .base import BaseWriter


class FileWriter(BaseWriter):
    """Appends each event as a JSON line to a local file.

    - Append-only: never overwrites existing entries
    - No external dependency: works offline, zero config
    - JSONL format: easy to pipe into jq, grep, or any log tool
    """

    def __init__(self, path: str = "./agentlens_audit.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")
