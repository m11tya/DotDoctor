from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dotdoctor.domain.models import CheckResult, ScanReport


def render_terminal_report(report: ScanReport, console: Console) -> None:
    table = Table(title=f"DotDoctor Scan ({report.profile})")
    table.add_column("Check ID", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Message")
    table.add_column("Remediation")

    for result in report.results:
        table.add_row(
            result.check_id,
            result.severity.value,
            result.message,
            result.remediation or "-",
        )

    summary = report.summary
    console.print(table)
    summary_line = (
        f"Summary: PASS={summary['PASS']} WARN={summary['WARN']} "
        f"FAIL={summary['FAIL']} | Exit={report.exit_code}"
    )
    console.print(summary_line)


def build_live_dashboard(
    profile: str,
    results: list[CheckResult],
    total_checks: int,
    elapsed_seconds: float,
    active_check_id: str | None,
) -> Layout:
    report = ScanReport(profile=profile, results=results)
    summary = report.summary

    header = Text(
        f"DotDoctor Live Scan  |  profile={profile}  |  elapsed={elapsed_seconds:.1f}s",
        style="bold cyan",
    )

    progress_table = Table.grid(expand=True)
    progress_table.add_column()
    progress_table.add_column(justify="right")
    completed = len(results)
    ratio = completed / total_checks if total_checks > 0 else 1.0
    bar_width = 30
    filled = int(ratio * bar_width)
    progress_bar = "[" + ("#" * filled) + ("-" * (bar_width - filled)) + "]"
    progress_table.add_row(
        f"Progress {progress_bar} {completed}/{total_checks}",
        f"PASS={summary['PASS']} WARN={summary['WARN']} FAIL={summary['FAIL']}",
    )

    state_message = f"Running: {active_check_id}" if active_check_id else "Completed"
    state_style = "yellow" if active_check_id else "green"

    rows_table = Table(expand=True)
    rows_table.add_column("Check", style="cyan", no_wrap=True)
    rows_table.add_column("Status", no_wrap=True)
    rows_table.add_column("Message")

    for result in results[-10:]:
        status_style = {
            "PASS": "green",
            "WARN": "yellow",
            "FAIL": "red",
        }.get(result.severity.value, "white")
        rows_table.add_row(
            result.check_id,
            f"[{status_style}]{result.severity.value}[/{status_style}]",
            result.message,
        )

    if not results:
        rows_table.add_row("-", "-", "Waiting for first check result...")

    layout = Layout()
    layout.split_column(
        Layout(Panel(Align.left(header), border_style="cyan"), size=3),
        Layout(Panel(progress_table, title="Scan Status", border_style="blue"), size=5),
        Layout(
            Panel(
                rows_table,
                title=f"Recent Results ({state_message})",
                border_style=state_style,
            )
        ),
    )
    return layout
