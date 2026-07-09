import os
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live

from dotdoctor.application.use_cases import RunScanUseCase
from dotdoctor.cli.render import build_live_dashboard, render_terminal_report
from dotdoctor.domain.context import ScanContext
from dotdoctor.domain.models import CheckResult, ScanReport
from dotdoctor.infrastructure.checks.registry import resolve_checks
from dotdoctor.infrastructure.config_loader import ConfigError, load_config

app = typer.Typer(help="DotDoctor: diagnose Linux development environment issues.")

PROFILE_OPTION = typer.Option("python-dev", help="Scan profile name.")
CONFIG_OPTION = typer.Option(
    None,
    "--config",
    help="Path to dotdoctor YAML config. Defaults to dotdoctor.yml or DOTDOCTOR_CONFIG.",
)
DISABLE_CHECK_OPTION = typer.Option(
    [],
    "--disable-check",
    help="Disable a check id for this run (can be repeated).",
)
JSON_OUTPUT_OPTION = typer.Option(
    None,
    "--json-output",
    help="Optional file path for machine-readable JSON report.",
)
UI_OPTION = typer.Option(
    False,
    "--ui/--no-ui",
    help="Use fullscreen live interface during scan.",
)


@app.callback(invoke_without_command=True)
def root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _scan_impl(
            profile="python-dev",
            config=None,
            disable_check=[],
            json_output=None,
            ui=True,
        )


@app.command("version")
def version() -> None:
    """Print DotDoctor version."""
    console = Console()
    console.print("dotdoctor 0.1.0")


@app.command("scan")
def scan(
    profile: str = PROFILE_OPTION,
    config: Path | None = CONFIG_OPTION,
    disable_check: list[str] = DISABLE_CHECK_OPTION,
    json_output: Path | None = JSON_OUTPUT_OPTION,
    ui: bool = UI_OPTION,
) -> None:
    _scan_impl(profile, config, disable_check, json_output, ui)


def _scan_impl(
    profile: str,
    config: Path | None,
    disable_check: list[str],
    json_output: Path | None,
    ui: bool,
) -> None:
    console = Console()

    try:
        loaded = load_config(config)
        selected_profile = loaded.profiles.get(profile)
        if selected_profile is None:
            available = ", ".join(sorted(loaded.profiles.keys()))
            raise ValueError(f"Unknown profile '{profile}'. Available: {available}")

        context = ScanContext(
            profile=profile,
            cwd=Path.cwd(),
            home=Path.home(),
            path_value=os.environ.get("PATH", ""),
            shell=os.environ.get("SHELL"),
        )

        use_case = RunScanUseCase(resolve_checks(selected_profile, set(disable_check)))
        report = _run_scan(use_case, context, console, ui=ui)

        if json_output is not None:
            json_output.parent.mkdir(parents=True, exist_ok=True)
            json_output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            console.print(f"JSON report exported to: {json_output}")

        raise typer.Exit(code=report.exit_code)
    except typer.Exit:
        raise
    except ConfigError as exc:
        console.print(f"[red]DotDoctor config error:[/red] {exc}")
        raise typer.Exit(code=3) from None
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]DotDoctor runtime error:[/red] {exc}")
        raise typer.Exit(code=3) from None


def _run_scan(
    use_case: RunScanUseCase,
    context: ScanContext,
    console: Console,
    ui: bool,
) -> ScanReport:
    if not ui:
        report = use_case.execute(context)
        render_terminal_report(report, console)
        return report

    results: list[CheckResult] = []
    total_checks = use_case.total_checks
    started = time.monotonic()

    with Live(
        build_live_dashboard(
            profile=context.profile,
            results=results,
            total_checks=total_checks,
            elapsed_seconds=0.0,
            active_check_id=None,
        ),
        console=console,
        screen=True,
        refresh_per_second=10,
    ) as live:
        for result in use_case.execute_iter(context):
            results.append(result)
            live.update(
                build_live_dashboard(
                    profile=context.profile,
                    results=results,
                    total_checks=total_checks,
                    elapsed_seconds=time.monotonic() - started,
                    active_check_id=result.check_id,
                )
            )

        live.update(
            build_live_dashboard(
                profile=context.profile,
                results=results,
                total_checks=total_checks,
                elapsed_seconds=time.monotonic() - started,
                active_check_id=None,
            )
        )

    report = ScanReport(profile=context.profile, results=results)
    render_terminal_report(report, console)
    return report
