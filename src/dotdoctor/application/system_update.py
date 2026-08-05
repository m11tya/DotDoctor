import os
import re
import shutil
import subprocess
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass

from rich.console import Console

from dotdoctor.domain.context import ScanContext
from dotdoctor.domain.models import CheckResult, ScanReport, Severity


@dataclass(frozen=True)
class _ExecResult:
    completed: subprocess.CompletedProcess[str] | None
    timed_out: bool = False


@dataclass(frozen=True)
class SystemCheckTask:
    check_id: str
    label: str
    runner: Callable[[], CheckResult | None]


class SystemDryRunService:
    """Runs parallel dry-run checks for package update availability."""

    def build_tasks(self, context: ScanContext) -> list[SystemCheckTask]:
        tasks: list[SystemCheckTask] = [
            SystemCheckTask(
                check_id="sys:packages",
                label="Checking Arch packages...",
                runner=lambda: self._check_arch_packages(context),
            ),
            SystemCheckTask(
                check_id="sys:flatpak",
                label="Scanning Flatpak packages...",
                runner=lambda: self._check_flatpak(context),
            ),
            SystemCheckTask(
                check_id="sys:firmware",
                label="Querying firmware updates...",
                runner=lambda: self._check_firmware(context),
            ),
        ]

        if shutil.which("yay") is not None:
            tasks.append(
                SystemCheckTask(
                    check_id="sys:aur",
                    label="Checking AUR packages...",
                    runner=lambda: self._check_aur_packages(context),
                )
            )

        omz_path = _resolve_oh_my_zsh_path(context)
        if omz_path is not None:
            tasks.append(
                SystemCheckTask(
                    check_id="sys:shell-omz",
                    label="Checking Oh-My-Zsh updates...",
                    runner=lambda: self._check_oh_my_zsh(omz_path),
                )
            )

        return tasks

    def run(self, context: ScanContext) -> ScanReport:
        tasks = self.build_tasks(context)
        results = self._run_tasks(tasks, on_task_complete=None)
        return ScanReport(profile=context.profile, results=results)

    def run_with_progress(
        self,
        context: ScanContext,
        on_task_complete: Callable[[str], None],
    ) -> ScanReport:
        tasks = self.build_tasks(context)
        results = self._run_tasks(tasks, on_task_complete=on_task_complete)
        return ScanReport(profile=context.profile, results=results)

    def _run_tasks(
        self,
        tasks: list[SystemCheckTask],
        on_task_complete: Callable[[str], None] | None,
    ) -> list[CheckResult]:
        if not tasks:
            return []

        ordered_results: dict[str, CheckResult | None] = {}
        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            futures: dict[Future[CheckResult | None], SystemCheckTask] = {
                pool.submit(task.runner): task for task in tasks
            }
            pending = set(futures.keys())
            while pending:
                done, pending = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
                for future in done:
                    task = futures[future]
                    ordered_results[task.check_id] = future.result()
                    if on_task_complete is not None:
                        on_task_complete(task.check_id)

        collected_results: list[CheckResult] = []
        for task in tasks:
            result = ordered_results.get(task.check_id)
            if result is not None:
                collected_results.append(result)
        return collected_results

    def _check_arch_packages(self, context: ScanContext) -> CheckResult:
        if shutil.which("checkupdates") is None:
            return CheckResult(
                check_id="sys:packages",
                severity=Severity.PASS,
                message="checkupdates is not installed; skipping Arch package update check.",
                remediation=None,
            )

        result = _run_capture(["checkupdates"], timeout=60)
        if result.timed_out:
            return CheckResult(
                check_id="sys:packages",
                severity=Severity.FAIL,
                message="checkupdates timed out — mirror or network connection failure.",
                remediation=(
                    "Run rate-mirrors or reflector to refresh your mirror list, " "then retry."
                ),
            )
        if result.completed is None:
            return CheckResult(
                check_id="sys:packages",
                severity=Severity.WARN,
                message="Could not run checkupdates.",
                remediation="Run checkupdates manually and inspect command health.",
            )
        completed = result.completed
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if completed.returncode == 2 or not lines:
            return _result_for_count("sys:packages", 0)

        if completed.returncode not in {0, 2}:
            return CheckResult(
                check_id="sys:packages",
                severity=Severity.FAIL,
                message="checkupdates failed — possible pacman database fetch error.",
                remediation="Verify mirror availability and run pacman -Sy manually.",
            )

        return _result_for_count("sys:packages", len(lines))

    def _check_flatpak(self, context: ScanContext) -> CheckResult:
        if shutil.which("flatpak") is None:
            return CheckResult(
                check_id="sys:flatpak",
                severity=Severity.PASS,
                message="flatpak is not installed; skipping Flatpak update check.",
                remediation=None,
            )

        result = _run_capture(["flatpak", "remote-ls", "--updates"], timeout=60)
        if result.timed_out:
            return CheckResult(
                check_id="sys:flatpak",
                severity=Severity.FAIL,
                message="Flatpak update check timed out — network connection failure.",
                remediation="Check network connectivity and retry.",
            )
        if result.completed is None:
            return CheckResult(
                check_id="sys:flatpak",
                severity=Severity.WARN,
                message="Could not run Flatpak update check.",
                remediation="Run flatpak remote-ls --updates manually.",
            )
        if result.completed.returncode != 0:
            return CheckResult(
                check_id="sys:flatpak",
                severity=Severity.FAIL,
                message=f"flatpak remote-ls failed (exit={result.completed.returncode}).",
                remediation="Check Flatpak remote configuration and network connectivity.",
            )
        lines = [line for line in result.completed.stdout.splitlines() if line.strip()]
        return _result_for_count("sys:flatpak", len(lines))

    def _check_firmware(self, context: ScanContext) -> CheckResult:
        if shutil.which("fwupdmgr") is None:
            return CheckResult(
                check_id="sys:firmware",
                severity=Severity.PASS,
                message="fwupdmgr is not installed; skipping firmware update check.",
                remediation=None,
            )

        refresh = _run_capture(["fwupdmgr", "refresh"], timeout=90)
        if refresh.timed_out:
            return CheckResult(
                check_id="sys:firmware",
                severity=Severity.FAIL,
                message="fwupdmgr refresh timed out — network connection failure.",
                remediation="Check network connectivity and retry.",
            )
        if refresh.completed is None:
            return CheckResult(
                check_id="sys:firmware",
                severity=Severity.WARN,
                message="Could not refresh firmware metadata.",
                remediation="Run fwupdmgr refresh manually.",
            )

        updates_result = _run_capture(["fwupdmgr", "get-updates"], timeout=90)
        if updates_result.timed_out:
            return CheckResult(
                check_id="sys:firmware",
                severity=Severity.FAIL,
                message="fwupdmgr get-updates timed out — network connection failure.",
                remediation="Check network connectivity and retry.",
            )
        if updates_result.completed is None:
            return CheckResult(
                check_id="sys:firmware",
                severity=Severity.WARN,
                message="Could not run firmware update check.",
                remediation="Run fwupdmgr get-updates manually.",
            )
        completed = updates_result.completed

        if completed.returncode == 2:
            return CheckResult(
                check_id="sys:firmware",
                severity=Severity.PASS,
                message="No firmware updates found",
                remediation=None,
                details={"updates": 0},
            )

        update_count = _parse_fwupdmgr_updates(completed.stdout)
        if completed.returncode not in {0, 2} and update_count == 0:
            return CheckResult(
                check_id="sys:firmware",
                severity=Severity.WARN,
                message="Firmware check returned an unexpected exit code.",
                remediation="Run fwupdmgr get-updates manually and inspect output.",
            )

        if update_count == 0:
            return CheckResult(
                check_id="sys:firmware",
                severity=Severity.PASS,
                message="No firmware updates found",
                remediation=None,
                details={"updates": 0},
            )

        return _result_for_count("sys:firmware", update_count)

    def _check_oh_my_zsh(self, omz_path: str) -> CheckResult:
        update_count = _detect_oh_my_zsh_updates(omz_path)
        if update_count > 0:
            return CheckResult(
                check_id="sys:shell-omz",
                severity=Severity.OUTD,
                message=f"Found {update_count} updates",
                remediation="Run dotdoctor --sysup to apply updates.",
                details={"updates": update_count},
            )

        return CheckResult(
            check_id="sys:shell-omz",
            severity=Severity.PASS,
            message="No updates found",
            remediation=None,
            details={"updates": 0},
        )

    def _check_aur_packages(self, context: ScanContext) -> CheckResult:
        result = _run_capture(["yay", "-Qua"], timeout=60)
        if result.timed_out:
            return CheckResult(
                check_id="sys:aur",
                severity=Severity.FAIL,
                message="AUR update check timed out — network or mirror failure.",
                remediation="Run rate-mirrors to refresh mirror list, then retry.",
            )
        if result.completed is None:
            return CheckResult(
                check_id="sys:aur",
                severity=Severity.WARN,
                message="Could not run AUR update check.",
                remediation="Run yay -Qua manually and inspect command health.",
            )
        lines = [line.strip() for line in result.completed.stdout.splitlines() if line.strip()]
        flagged = [line for line in lines if _AUR_FLAGGED_RE.search(line)]
        regular = [line for line in lines if line not in flagged]

        if not lines:
            return CheckResult(
                check_id="sys:aur",
                severity=Severity.PASS,
                message="No AUR updates found.",
                remediation=None,
                details={"updates": 0, "flagged": 0},
            )
        if flagged:
            return CheckResult(
                check_id="sys:aur",
                severity=Severity.OUTD,
                message=(
                    f"Found {len(regular)} AUR update(s) and {len(flagged)} "
                    "flagged out-of-date package(s)."
                ),
                remediation=(
                    "Run dotdoctor --sysup to apply available AUR updates. "
                    "Flagged packages require upstream or maintainer action."
                ),
                details={"updates": len(regular), "flagged": len(flagged)},
            )
        return CheckResult(
            check_id="sys:aur",
            severity=Severity.OUTD,
            message=f"Found {len(regular)} AUR update(s).",
            remediation="Run dotdoctor --sysup to apply updates.",
            details={"updates": len(regular), "flagged": 0},
        )


def _result_for_count(check_id: str, updates: int) -> CheckResult:
    if updates > 0:
        return CheckResult(
            check_id=check_id,
            severity=Severity.OUTD,
            message=f"Found {updates} updates",
            remediation="Run dotdoctor --sysup to apply updates.",
            details={"updates": updates},
        )

    return CheckResult(
        check_id=check_id,
        severity=Severity.PASS,
        message="No updates found",
        remediation=None,
        details={"updates": 0},
    )


_NETWORK_FAILURE_PATTERNS: frozenset[str] = frozenset(
    {
        "failed to retrieve",
        "failed to synchronize",
        "couldn't connect to server",
        "connection timed out",
        "download library error",
        "error: failed to update",
        "failed to download",
        "curl error",
        "resolving timed out",
        "failed to get",
        "could not connect",
    }
)

_AUR_FLAGGED_RE = re.compile(
    r"\[(?:out[- ]of[- ]date|flagged[- ]out[- ]of[- ]date)\b",
    re.IGNORECASE,
)


def _is_mirror_failure(output: str) -> bool:
    lowered = output.lower()
    return any(pattern in lowered for pattern in _NETWORK_FAILURE_PATTERNS)


def _run_capture(command: list[str], timeout: int) -> _ExecResult:
    try:
        return _ExecResult(
            completed=subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        )
    except subprocess.TimeoutExpired:
        return _ExecResult(completed=None, timed_out=True)
    except (OSError, subprocess.SubprocessError):
        return _ExecResult(completed=None, timed_out=False)


def _resolve_oh_my_zsh_path(context: ScanContext) -> str | None:
    zsh_env = os.environ.get("ZSH")
    if zsh_env:
        env_path = os.path.expanduser(zsh_env)
        if os.path.isdir(env_path):
            return env_path

    default_path = context.home / ".oh-my-zsh"
    if default_path.exists() and default_path.is_dir():
        return str(default_path)

    return None


def _detect_oh_my_zsh_updates(omz_path: str) -> int:
    if shutil.which("git") is None:
        return 0

    git_dir = os.path.join(omz_path, ".git")
    if not os.path.isdir(git_dir):
        return 0

    _run_capture(["git", "-C", omz_path, "fetch", "--quiet", "origin"], timeout=30)
    count_result = _run_capture(
        ["git", "-C", omz_path, "rev-list", "--count", "HEAD..origin/master"],
        timeout=30,
    )
    if count_result.completed is None or count_result.completed.returncode != 0:
        return 0

    raw = count_result.completed.stdout.strip()
    if not raw.isdigit():
        return 0
    return int(raw)


class SystemUpgradeService:
    """Runs sequential interactive system update commands."""

    def run(self, context: ScanContext, console: Console) -> int:
        console.print("[cyan]Caching sudo credentials...[/cyan]")
        sudo_cache = subprocess.run(["sudo", "true"], check=False)
        if sudo_cache.returncode != 0:
            console.print("[red]Failed to cache sudo credentials. Aborting update phase.[/red]")
            return 3

        had_error = False
        had_error |= self._refresh_mirrors(console)

        if shutil.which("yay") is not None:
            yay_error, is_net_failure = self._run_step(
                ["yay", "-Syu", "--noconfirm"],
                console,
                "System and AUR update",
            )
            if yay_error and is_net_failure:
                console.print(
                    "[yellow]Mirror or network failure detected. "
                    "Attempting mirror recovery...[/yellow]"
                )
                mirror_failed = self._refresh_mirrors(console)
                if mirror_failed:
                    console.print(
                        "[red]FAIL: Mirror recovery failed. Package upgrade aborted.[/red]"
                    )
                    return 1
                retry_error, _ = self._run_step(
                    ["yay", "-Syu", "--noconfirm"],
                    console,
                    "System and AUR update (retry after mirror recovery)",
                )
                if retry_error:
                    console.print(
                        "[red]FAIL: Package upgrade aborted — persistent network failure.[/red]"
                    )
                    return 1
            elif yay_error:
                had_error = True
        else:
            console.print("[dim]Skipping yay update: component is not installed.[/dim]")

        if shutil.which("flatpak") is not None:
            flatpak_error, _ = self._run_step(
                ["flatpak", "update", "-y"], console, "Flatpak update"
            )
            had_error |= flatpak_error
        else:
            console.print("[dim]Skipping Flatpak update: component is not installed.[/dim]")

        omz_upgrade = context.home / ".oh-my-zsh" / "tools" / "upgrade.sh"
        if omz_upgrade.exists():
            omz_error, _ = self._run_step(
                ["sh", str(omz_upgrade)],
                console,
                "Oh-My-Zsh update",
            )
            had_error |= omz_error
        else:
            console.print("[dim]Skipping Oh-My-Zsh update: component is not installed.[/dim]")

        if shutil.which("fwupdmgr") is not None:
            fw_error, _ = self._run_step(["fwupdmgr", "update", "-y"], console, "Firmware update")
            had_error |= fw_error
        else:
            console.print("[dim]Skipping firmware update: component is not installed.[/red]")

        if had_error:
            console.print("[yellow]System update finished with warnings/errors.[/yellow]")
            return 2

        console.print("[green]System update completed successfully![/green]")
        return 0

    def _refresh_mirrors(self, console: Console) -> bool:
        if shutil.which("cachyos-rate-mirrors") is not None:
            had_error, _ = self._run_step(
                ["sudo", "cachyos-rate-mirrors"],
                console,
                "Mirror refresh (cachyos-rate-mirrors)",
            )
            return had_error

        if shutil.which("reflector") is not None:
            had_error, _ = self._run_step(
                [
                    "sudo",
                    "reflector",
                    "--latest",
                    "5",
                    "--protocol",
                    "https",
                    "--sort",
                    "rate",
                    "--save",
                    "/etc/pacman.d/mirrorlist",
                ],
                console,
                "Mirror refresh (reflector)",
            )
            return had_error

        console.print("[dim]Skipping mirror refresh: no supported mirror tool installed.[/dim]")
        return False

    def _run_step(self, command: list[str], console: Console, title: str) -> tuple[bool, bool]:
        console.print(f"[cyan]Running:[/cyan] {title}")
        try:
            completed = subprocess.run(command, check=False, stderr=subprocess.PIPE, text=True)
        except subprocess.TimeoutExpired:
            console.print(f"[red]{title} timed out.[/red]")
            return True, True
        except (OSError, subprocess.SubprocessError) as exc:
            console.print(f"[red]{title} failed to start: {exc}.[/red]")
            return True, False

        if completed.returncode != 0:
            is_net_failure = _is_mirror_failure(completed.stderr)
            console.print(f"[red]{title} failed (exit={completed.returncode}).[/red]")
            return True, is_net_failure
        return False, False


def _parse_fwupdmgr_updates(output: str) -> int:
    """Count firmware updates only when there are explicit update indicators."""
    lines = [line.rstrip() for line in output.splitlines()]
    normalized = "\n".join(line.lower() for line in lines)

    no_update_markers = (
        "no updates available",
        "no updatable devices",
        "devices with the latest available firmware version",
        "devices with no available firmware updates",
    )
    if any(marker in normalized for marker in no_update_markers):
        # Continue scanning only for explicit updates, but default to 0.
        pass

    version_transition_pattern = re.compile(r"\b\d[\w.-]*\s*(?:->|→)\s*\d[\w.-]*\b")
    explicit_update_pattern = re.compile(
        r"\b(update available for|updates available for|upgrade available for)\b",
    )

    updates = 0
    in_no_update_section = False
    for raw_line in lines:
        line = raw_line.strip()
        lowered = line.lower()
        if not line:
            in_no_update_section = False
            continue

        if lowered.startswith("devices with the latest available firmware version"):
            in_no_update_section = True
            continue

        if lowered.startswith("devices with no available firmware updates"):
            in_no_update_section = True
            continue

        if in_no_update_section:
            continue

        if version_transition_pattern.search(line):
            updates += 1
            continue

        if explicit_update_pattern.search(lowered):
            updates += 1

    return updates
