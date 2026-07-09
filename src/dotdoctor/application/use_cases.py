from collections.abc import Iterator

from dotdoctor.domain.context import ScanContext
from dotdoctor.domain.models import CheckResult, ScanReport, Severity
from dotdoctor.domain.ports import EnvironmentCheck


class RunScanUseCase:
    def __init__(self, checks: list[EnvironmentCheck]) -> None:
        self._checks = checks

    @property
    def total_checks(self) -> int:
        return len(self._checks)

    def execute_iter(self, context: ScanContext) -> Iterator[CheckResult]:
        for check in self._checks:
            yield self._run_single_check(check, context)

    def execute(self, context: ScanContext) -> ScanReport:
        results = list(self.execute_iter(context))

        return ScanReport(profile=context.profile, results=results)

    def _run_single_check(self, check: EnvironmentCheck, context: ScanContext) -> CheckResult:
        try:
            return check.run(context)
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=check.check_id,
                severity=Severity.FAIL,
                message="DotDoctor check execution failed",
                remediation=(
                    "Inspect check logs and retry. " "If issue persists, open a bug report."
                ),
                details={"exception": type(exc).__name__, "error": str(exc)},
            )
