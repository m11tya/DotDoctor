from typing import Protocol

from dotdoctor.domain.context import ScanContext
from dotdoctor.domain.models import CheckResult


class EnvironmentCheck(Protocol):
    check_id: str

    def run(self, context: ScanContext) -> CheckResult: ...
