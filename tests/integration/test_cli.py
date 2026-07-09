from pathlib import Path

from typer.testing import CliRunner

from dotdoctor.cli.app import app

runner = CliRunner()


def test_cli_scan_pass_exit_code(tmp_path: Path) -> None:
    config = tmp_path / "dotdoctor.yml"
    config.write_text(
        """
profiles:
  python-dev:
    enabled_checks:
      - path.integrity
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["scan", "--config", str(config)], env={"PATH": "/usr/bin"})

    assert result.exit_code == 0


def test_cli_scan_warn_exit_code(tmp_path: Path) -> None:
    config = tmp_path / "dotdoctor.yml"
    config.write_text(
        """
profiles:
  python-dev:
    enabled_checks:
      - path.integrity
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["scan", "--config", str(config)], env={"PATH": "/missing/path"})

    assert result.exit_code == 1


def test_cli_scan_fail_exit_code_for_missing_binary(tmp_path: Path) -> None:
    config = tmp_path / "dotdoctor.yml"
    config.write_text(
        """
profiles:
  python-dev:
    enabled_checks:
      - binary.supermissing
    required_binaries:
      - name: supermissing
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["scan", "--config", str(config)], env={"PATH": "/usr/bin"})

    assert result.exit_code == 2


def test_cli_invalid_config_returns_runtime_error_code(tmp_path: Path) -> None:
    config = tmp_path / "invalid.yml"
    config.write_text("profiles: [", encoding="utf-8")

    result = runner.invoke(app, ["scan", "--config", str(config)], env={"PATH": "/usr/bin"})

    assert result.exit_code == 3
