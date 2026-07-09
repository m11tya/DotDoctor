from pathlib import Path

from dotdoctor.application.use_cases import RunScanUseCase
from dotdoctor.domain.context import ScanContext
from dotdoctor.domain.models import CheckResult, Severity


class BoomCheck:
    check_id = "boom"

    def run(self, context: ScanContext) -> CheckResult:
        raise RuntimeError("kaboom")


def test_use_case_converts_unhandled_check_exception_to_fail() -> None:
    use_case = RunScanUseCase([BoomCheck()])
    context = ScanContext(
        profile="python-dev",
        cwd=Path.cwd(),
        home=Path.home(),
        path_value="/usr/bin",
        shell="/bin/zsh",
    )

    report = use_case.execute(context)

    assert report.results[0].severity is Severity.FAIL
    assert report.results[0].check_id == "boom"
    assert report.exit_code == 2
