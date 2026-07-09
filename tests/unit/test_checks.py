import stat
from pathlib import Path

from dotdoctor.domain.config import BinaryRequirement, ProfileConfig
from dotdoctor.domain.context import ScanContext
from dotdoctor.domain.models import Severity
from dotdoctor.infrastructure.checks.core import BinaryCheck, PathIntegrityCheck, PermissionsCheck


def _context(path_value: str) -> ScanContext:
    return ScanContext(
        profile="python-dev",
        cwd=Path.cwd(),
        home=Path.home(),
        path_value=path_value,
        shell="/bin/zsh",
    )


def test_missing_binary_returns_fail(monkeypatch) -> None:
    check = BinaryCheck(BinaryRequirement(name="missing-tool"))
    monkeypatch.setattr("dotdoctor.infrastructure.checks.core.shutil.which", lambda _: None)

    result = check.run(_context("/usr/bin"))

    assert result.severity is Severity.FAIL


def test_version_below_minimum_returns_fail(monkeypatch) -> None:
    check = BinaryCheck(BinaryRequirement(name="git", min_version="2.30"))

    monkeypatch.setattr(
        "dotdoctor.infrastructure.checks.core.shutil.which",
        lambda _: "/usr/bin/git",
    )

    class Completed:
        stdout = "git version 2.10.1"
        stderr = ""

    monkeypatch.setattr(
        "dotdoctor.infrastructure.checks.core.subprocess.run",
        lambda *args, **kwargs: Completed(),
    )

    result = check.run(_context("/usr/bin"))

    assert result.severity is Severity.FAIL
    assert "required" in result.details


def test_path_check_warns_on_broken_entry() -> None:
    check = PathIntegrityCheck()
    result = check.run(_context("/usr/bin:/definitely/missing/path"))

    assert result.severity is Severity.WARN
    assert result.details["missing_entries"]


def test_permission_denied_returns_fail(tmp_path: Path) -> None:
    denied_dir = tmp_path / "denied"
    denied_dir.mkdir()
    denied_dir.chmod(0)

    check = PermissionsCheck(
        ProfileConfig(enabled_checks=["permissions.dev_dirs"], permission_paths=[str(denied_dir)])
    )

    try:
        result = check.run(_context("/usr/bin"))
        assert result.severity in {Severity.FAIL, Severity.WARN}
    finally:
        denied_dir.chmod(stat.S_IRWXU)
