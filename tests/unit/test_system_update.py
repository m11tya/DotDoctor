import subprocess
from pathlib import Path
from types import SimpleNamespace

from dotdoctor.application.system_update import SystemDryRunService, SystemUpgradeService
from dotdoctor.domain.context import ScanContext
from dotdoctor.domain.models import Severity


class DummyConsole:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def print(self, message: str) -> None:
        self.messages.append(message)


def _context(tmp_path: Path) -> ScanContext:
    return ScanContext(
        profile="system",
        cwd=tmp_path,
        home=tmp_path,
        path_value="/usr/bin",
        shell="/bin/bash",
    )


def test_system_dry_run_marks_outd_when_updates_detected(monkeypatch, tmp_path: Path) -> None:
    service = SystemDryRunService()

    def fake_which(name: str) -> str | None:
        return f"/usr/bin/{name}"

    def fake_run(*args, **kwargs):
        command = args[0]
        if command[:1] == ["checkupdates"]:
            return SimpleNamespace(stdout="pkg1\npkg2\n", returncode=0)
        if command[:3] == ["flatpak", "remote-ls", "--updates"]:
            return SimpleNamespace(stdout="app.one\n", returncode=0)
        if command[:2] == ["fwupdmgr", "refresh"]:
            return SimpleNamespace(stdout="", returncode=0)
        if command[:2] == ["fwupdmgr", "get-updates"]:
            return SimpleNamespace(stdout="1.2.3 -> 1.2.4\n", returncode=0)
        if command[:2] == ["yay", "-Qua"]:
            return SimpleNamespace(stdout="aur/pkg-a 1.0-1 2.0-1\n", returncode=0)
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("dotdoctor.application.system_update.shutil.which", fake_which)
    monkeypatch.setattr("dotdoctor.application.system_update.subprocess.run", fake_run)

    (tmp_path / ".oh-my-zsh").mkdir()
    report = service.run(_context(tmp_path))

    by_id = {item.check_id: item for item in report.results}
    assert by_id["sys:packages"].severity is Severity.OUTD
    assert by_id["sys:flatpak"].severity is Severity.OUTD
    assert by_id["sys:firmware"].severity is Severity.OUTD
    assert by_id["sys:aur"].severity is Severity.OUTD
    assert by_id["sys:shell-omz"].severity is Severity.PASS


def test_system_dry_run_skips_missing_components(monkeypatch, tmp_path: Path) -> None:
    service = SystemDryRunService()
    monkeypatch.setattr("dotdoctor.application.system_update.shutil.which", lambda _: None)

    report = service.run(_context(tmp_path))

    assert "sys:shell-omz" not in {item.check_id for item in report.results}
    assert all(item.severity is Severity.PASS for item in report.results)


def test_system_dry_run_omz_uses_zsh_env_and_detects_updates(monkeypatch, tmp_path: Path) -> None:
    service = SystemDryRunService()
    omz = tmp_path / "custom-omz"
    (omz / ".git").mkdir(parents=True)

    monkeypatch.setenv("ZSH", str(omz))

    def fake_which(name: str) -> str | None:
        if name in {"git"}:
            return f"/usr/bin/{name}"
        return None

    def fake_run(*args, **kwargs):
        command = args[0]
        if command[:3] == ["git", "-C", str(omz)] and command[3:] == ["fetch", "--quiet", "origin"]:
            return SimpleNamespace(stdout="", returncode=0)
        if command[:3] == ["git", "-C", str(omz)] and command[3:] == [
            "rev-list",
            "--count",
            "HEAD..origin/master",
        ]:
            return SimpleNamespace(stdout="2\n", returncode=0)
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("dotdoctor.application.system_update.shutil.which", fake_which)
    monkeypatch.setattr("dotdoctor.application.system_update.subprocess.run", fake_run)

    report = service.run(_context(tmp_path))
    by_id = {item.check_id: item for item in report.results}
    assert by_id["sys:shell-omz"].severity is Severity.OUTD


def test_system_dry_run_treats_checkupdates_exit_two_as_no_updates(
    monkeypatch,
    tmp_path: Path,
) -> None:
    service = SystemDryRunService()

    def fake_which(name: str) -> str | None:
        if name == "checkupdates":
            return "/usr/bin/checkupdates"
        return None

    def fake_run(*args, **kwargs):
        command = args[0]
        if command[:1] == ["checkupdates"]:
            return SimpleNamespace(stdout="", returncode=2)
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("dotdoctor.application.system_update.shutil.which", fake_which)
    monkeypatch.setattr("dotdoctor.application.system_update.subprocess.run", fake_run)

    report = service.run(_context(tmp_path))
    by_id = {item.check_id: item for item in report.results}
    assert by_id["sys:packages"].severity is Severity.PASS


def test_system_dry_run_firmware_latest_available_is_not_counted_as_updates(
    monkeypatch,
    tmp_path: Path,
) -> None:
    service = SystemDryRunService()

    def fake_which(name: str) -> str | None:
        if name == "fwupdmgr":
            return "/usr/bin/fwupdmgr"
        return None

    def fake_run(*args, **kwargs):
        command = args[0]
        if command[:2] == ["fwupdmgr", "refresh"]:
            return SimpleNamespace(stdout="", returncode=0)
        if command[:2] == ["fwupdmgr", "get-updates"]:
            return SimpleNamespace(
                stdout=(
                    "Devices with the latest available firmware version:\n"
                    "  Device A\n"
                    "\n"
                    "Devices with no available firmware updates:\n"
                    "  Device B\n"
                ),
                returncode=0,
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("dotdoctor.application.system_update.shutil.which", fake_which)
    monkeypatch.setattr("dotdoctor.application.system_update.subprocess.run", fake_run)

    report = service.run(_context(tmp_path))
    by_id = {item.check_id: item for item in report.results}
    assert by_id["sys:firmware"].severity is Severity.PASS
    assert by_id["sys:firmware"].message == "No firmware updates found"


def test_system_dry_run_firmware_detects_explicit_version_transition(
    monkeypatch,
    tmp_path: Path,
) -> None:
    service = SystemDryRunService()

    def fake_which(name: str) -> str | None:
        if name == "fwupdmgr":
            return "/usr/bin/fwupdmgr"
        return None

    def fake_run(*args, **kwargs):
        command = args[0]
        if command[:2] == ["fwupdmgr", "refresh"]:
            return SimpleNamespace(stdout="", returncode=0)
        if command[:2] == ["fwupdmgr", "get-updates"]:
            return SimpleNamespace(
                stdout=(
                    "Device: Sample Device\n"
                    "Current version: 1.2.3\n"
                    "1.2.3 -> 1.2.4\n"
                ),
                returncode=0,
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("dotdoctor.application.system_update.shutil.which", fake_which)
    monkeypatch.setattr("dotdoctor.application.system_update.subprocess.run", fake_run)

    report = service.run(_context(tmp_path))
    by_id = {item.check_id: item for item in report.results}
    assert by_id["sys:firmware"].severity is Severity.OUTD


def test_system_upgrade_runs_steps_and_reports_success(monkeypatch, tmp_path: Path) -> None:
    service = SystemUpgradeService()
    console = DummyConsole()

    commands: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        if name in {"yay", "flatpak", "fwupdmgr", "cachyos-rate-mirrors"}:
            return f"/usr/bin/{name}"
        return None

    def fake_run(*args, **kwargs):
        command = args[0]
        commands.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("dotdoctor.application.system_update.shutil.which", fake_which)
    monkeypatch.setattr("dotdoctor.application.system_update.subprocess.run", fake_run)

    omz_dir = tmp_path / ".oh-my-zsh" / "tools"
    omz_dir.mkdir(parents=True)
    (omz_dir / "upgrade.sh").write_text("echo upgrade", encoding="utf-8")

    code = service.run(_context(tmp_path), console)

    assert code == 0
    assert ["sudo", "true"] in commands
    assert ["sudo", "cachyos-rate-mirrors"] in commands
    assert ["yay", "-Syu", "--noconfirm"] in commands
    assert ["flatpak", "update", "-y"] in commands
    assert ["fwupdmgr", "update", "-y"] in commands
    assert ["sh", str(omz_dir / "upgrade.sh")] in commands


def test_check_aur_detects_flagged_packages(monkeypatch, tmp_path: Path) -> None:
    service = SystemDryRunService()

    def fake_which(name: str) -> str | None:
        if name == "yay":
            return "/usr/bin/yay"
        return None

    def fake_run(*args, **kwargs):
        command = args[0]
        if command[:2] == ["yay", "-Qua"]:
            return SimpleNamespace(
                stdout="aur/pkg-a 1.0-1 2.0-1\naur/pkg-b 3.0-1 [out-of-date]\n",
                returncode=0,
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("dotdoctor.application.system_update.shutil.which", fake_which)
    monkeypatch.setattr("dotdoctor.application.system_update.subprocess.run", fake_run)

    report = service.run(_context(tmp_path))
    by_id = {item.check_id: item for item in report.results}
    assert by_id["sys:aur"].severity is Severity.OUTD
    assert by_id["sys:aur"].details["flagged"] == 1
    assert by_id["sys:aur"].details["updates"] == 1


def test_check_arch_timeout_produces_fail(monkeypatch, tmp_path: Path) -> None:
    service = SystemDryRunService()

    def fake_which(name: str) -> str | None:
        if name == "checkupdates":
            return "/usr/bin/checkupdates"
        return None

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=60)

    monkeypatch.setattr("dotdoctor.application.system_update.shutil.which", fake_which)
    monkeypatch.setattr("dotdoctor.application.system_update.subprocess.run", fake_run)

    report = service.run(_context(tmp_path))
    by_id = {item.check_id: item for item in report.results}
    assert by_id["sys:packages"].severity is Severity.FAIL


def test_system_upgrade_network_failure_triggers_mirror_recovery(
    monkeypatch, tmp_path: Path
) -> None:
    service = SystemUpgradeService()
    console = DummyConsole()
    commands: list[list[str]] = []
    yay_attempt = [0]

    def fake_which(name: str) -> str | None:
        if name in {"yay", "cachyos-rate-mirrors"}:
            return f"/usr/bin/{name}"
        return None

    def fake_run(*args, **kwargs):
        command = args[0]
        commands.append(command)
        if command == ["sudo", "true"]:
            return SimpleNamespace(returncode=0, stderr="")
        if command == ["sudo", "cachyos-rate-mirrors"]:
            return SimpleNamespace(returncode=0, stderr="")
        if command == ["yay", "-Syu", "--noconfirm"]:
            yay_attempt[0] += 1
            if yay_attempt[0] == 1:
                return SimpleNamespace(returncode=1, stderr="failed to retrieve some files")
            return SimpleNamespace(returncode=0, stderr="")
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("dotdoctor.application.system_update.shutil.which", fake_which)
    monkeypatch.setattr("dotdoctor.application.system_update.subprocess.run", fake_run)

    code = service.run(_context(tmp_path), console)

    yay_calls = sum(1 for c in commands if c == ["yay", "-Syu", "--noconfirm"])
    mirror_calls = sum(1 for c in commands if c == ["sudo", "cachyos-rate-mirrors"])
    assert yay_calls == 2
    assert mirror_calls == 2
    assert code == 0
    assert any("mirror" in msg.lower() or "network" in msg.lower() for msg in console.messages)


def test_system_upgrade_fatal_network_error_returns_exit_one(
    monkeypatch, tmp_path: Path
) -> None:
    service = SystemUpgradeService()
    console = DummyConsole()

    def fake_which(name: str) -> str | None:
        if name in {"yay", "cachyos-rate-mirrors"}:
            return f"/usr/bin/{name}"
        return None

    def fake_run(*args, **kwargs):
        command = args[0]
        if command == ["sudo", "true"]:
            return SimpleNamespace(returncode=0, stderr="")
        if command == ["sudo", "cachyos-rate-mirrors"]:
            return SimpleNamespace(returncode=0, stderr="")
        if command == ["yay", "-Syu", "--noconfirm"]:
            return SimpleNamespace(returncode=1, stderr="failed to retrieve some files")
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("dotdoctor.application.system_update.shutil.which", fake_which)
    monkeypatch.setattr("dotdoctor.application.system_update.subprocess.run", fake_run)

    code = service.run(_context(tmp_path), console)
    assert code == 1
    assert any("FAIL" in msg for msg in console.messages)
