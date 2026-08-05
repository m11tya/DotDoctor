from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dotdoctor.domain.models import CheckResult, ScanReport


def _status_style(status: str) -> str:
    return {
        "PASS": "green",
        "OUTD": "blue",
        "WARN": "yellow",
        "FAIL": "red",
    }.get(status, "white")


def _summary_text(summary: dict[str, int], exit_code: int) -> Text:
    text = Text("Summary: ")
    text.append(f"PASS={summary['PASS']}", style="green")
    text.append(" ")
    text.append(f"OUTD={summary.get('OUTD', 0)}", style="blue")
    text.append(" ")
    text.append(f"WARN={summary['WARN']}", style="yellow")
    text.append(" ")
    text.append(f"FAIL={summary['FAIL']}", style="red")
    text.append(" | ")

    exit_style = "green" if exit_code == 0 else ("yellow" if exit_code == 1 else "red")
    text.append(f"Exit={exit_code}", style=exit_style)
    return text


def render_terminal_report(report: ScanReport, console: Console) -> None:
    table = Table(title=f"DotDoctor Scan ({report.profile})")
    table.add_column("Check ID")
    table.add_column("Status", style="bold")
    table.add_column("Message")
    table.add_column("Remediation")

    for result in report.results:
        status_style = f"bold {_status_style(result.severity.value)}"
        status_text = Text(result.severity.value, style=status_style)
        remediation_text = (
            Text(result.remediation, style="cyan") if result.remediation else Text("-")
        )
        table.add_row(
            result.check_id,
            status_text,
            result.message,
            remediation_text,
        )

    summary = report.summary
    console.print(table)
    console.print(_summary_text(summary, report.exit_code))


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
        (
            f"PASS={summary['PASS']} OUTD={summary.get('OUTD', 0)} "
            f"WARN={summary['WARN']} FAIL={summary['FAIL']}"
        ),
    )

    state_message = f"Running: {active_check_id}" if active_check_id else "Completed"
    state_style = "yellow" if active_check_id else "green"

    rows_table = Table(expand=True)
    rows_table.add_column("Check", style="cyan", no_wrap=True)
    rows_table.add_column("Status", no_wrap=True)
    rows_table.add_column("Message")

    for result in results[-10:]:
        status_style = _status_style(result.severity.value)
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
