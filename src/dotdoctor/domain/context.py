from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScanContext:
    profile: str
    cwd: Path
    home: Path
    path_value: str
    shell: str | None
