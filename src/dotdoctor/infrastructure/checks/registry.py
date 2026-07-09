from dotdoctor.domain.config import ProfileConfig
from dotdoctor.domain.ports import EnvironmentCheck
from dotdoctor.infrastructure.checks.core import (
    BinaryCheck,
    PathIntegrityCheck,
    PermissionsCheck,
    ShellConfigCheck,
)


def resolve_checks(
    profile: ProfileConfig,
    disabled_checks: set[str] | None = None,
) -> list[EnvironmentCheck]:
    disabled = disabled_checks or set()

    binary_checks = {
        f"binary.{requirement.name}": BinaryCheck(requirement)
        for requirement in profile.required_binaries
    }
    available_checks: dict[str, EnvironmentCheck] = {
        **binary_checks,
        "path.integrity": PathIntegrityCheck(),
        "shell.config": ShellConfigCheck(profile),
        "permissions.dev_dirs": PermissionsCheck(profile),
    }

    checks: list[EnvironmentCheck] = []
    for check_id in profile.enabled_checks:
        if check_id in disabled:
            continue

        check = available_checks.get(check_id)
        if check is not None:
            checks.append(check)

    return checks
