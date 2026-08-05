import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import typer
from rich.console import Console

from dotdoctor.domain.context import ScanContext
from dotdoctor.domain.models import CheckResult, ScanReport, Severity


@dataclass
class FixOutcome:
    changed: bool
    note: str


class InteractiveAutoFixer:
    """Interactive auto-fix orchestrator for WARN/FAIL findings."""

    _prefs_filename = ".dotdoctor.fix.json"
    _path_block_start = "# >>> dotdoctor path cleanup >>>"
    _path_block_end = "# <<< dotdoctor path cleanup <<<"

    def __init__(self, console: Console) -> None:
        self._console = console
        self._selected_shell: str | None = None

    def apply(self, report: ScanReport, context: ScanContext) -> ScanReport:
        results = list(report.results)
        changed_any = False
        had_issues = False

        for index, result in enumerate(results):
            if result.severity is Severity.PASS:
                continue

            had_issues = True

            prompt = self._build_prompt_message(result)
            should_fix = typer.confirm(prompt, default=True)
            if not should_fix:
                self._console.print("[dim]Skipped by user.[/dim]")
                continue

            fix_handler = self._resolve_fix_handler(result.check_id)
            if fix_handler is None:
                self._console.print(
                    f"[yellow]No automated fixer is registered for {result.check_id} yet.[/yellow]"
                )
                continue

            try:
                outcome = fix_handler(context, result)
            except OSError as exc:
                self._console.print(f"[red]Auto-fix failed:[/red] {exc}")
                continue

            if outcome.changed:
                changed_any = True
                self._console.print(f"[green]FIXED[/green] {result.check_id}: {outcome.note}")
                results[index] = CheckResult(
                    check_id=result.check_id,
                    severity=Severity.PASS,
                    message=f"Auto-fixed: {outcome.note}",
                    remediation=None,
                    details={**result.details, "auto_fixed": True},
                )
            else:
                self._console.print(f"[yellow]No changes applied[/yellow] for {result.check_id}: {outcome.note}")

        if not had_issues:
            self._console.print("[green]Nothing to fix. All checks are PASS.[/green]")
        elif changed_any:
            self._console.print("[green]Auto-fix phase completed.[/green]")
        return ScanReport(profile=report.profile, results=results)

    def _resolve_fix_handler(
        self,
        check_id: str,
    ) -> Callable[[ScanContext, CheckResult], FixOutcome] | None:
        handlers: dict[str, Callable[[ScanContext, CheckResult], FixOutcome]] = {
            "path.integrity": self._fix_path_integrity,
        }
        return handlers.get(check_id)

    def _build_prompt_message(self, result: CheckResult) -> str:
        duplicates = result.details.get("duplicate_entries", [])
        missing = result.details.get("missing_entries", [])
        empty_segments = result.details.get("empty_segments", "")

        if duplicates:
            return "Duplicate PATH entries detected. Clean shell configuration now?"
        if missing:
            return "Broken PATH entries detected. Remove them from shell configuration now?"
        if empty_segments:
            return "Empty PATH segments detected. Rewrite shell PATH export now?"
        if result.check_id != "path.integrity":
            return (
                f"Issue found in {result.check_id}. "
                "Try automated remediation if available?"
            )
        return "PATH issues detected. Apply automatic cleanup now?"

    def _fix_path_integrity(self, context: ScanContext, result: CheckResult) -> FixOutcome:
        raw_entries = context.path_value.split(":") if context.path_value else []
        cleaned: list[str] = []
        seen: set[str] = set()

        removed_empty = 0
        removed_duplicates = 0
        removed_missing = 0

        for entry in raw_entries:
            if not entry:
                removed_empty += 1
                continue

            normalized = str(Path(entry).expanduser().resolve(strict=False))
            if normalized in seen:
                removed_duplicates += 1
                continue

            if not Path(normalized).exists():
                removed_missing += 1
                continue

            seen.add(normalized)
            cleaned.append(normalized)

        if not cleaned:
            return FixOutcome(changed=False, note="Refused to write empty PATH to shell config.")

        shell_rc = self._resolve_shell_config(context)
        original = shell_rc.read_text(encoding="utf-8") if shell_rc.exists() else ""
        updated = self._upsert_managed_path_block(original, cleaned)

        if updated == original:
            return FixOutcome(changed=False, note="PATH block already up to date.")

        self._backup_file(shell_rc)
        shell_rc.write_text(updated, encoding="utf-8")

        summary = (
            f"Updated {shell_rc} (removed empty={removed_empty}, "
            f"duplicates={removed_duplicates}, missing={removed_missing})."
        )
        return FixOutcome(changed=True, note=summary)

    def _resolve_shell_config(self, context: ScanContext) -> Path:
        prefs = self._load_preferences(context.home)

        if self._selected_shell is None:
            preferred = prefs.get("shell")
            if preferred in {"bash", "zsh"}:
                self._selected_shell = preferred
            else:
                default_shell = "zsh" if (context.shell or "").endswith("zsh") else "bash"
                picked = typer.prompt(
                    "Choose shell config for auto-fix updates (bash/zsh)",
                    default=default_shell,
                ).strip().lower()
                self._selected_shell = "zsh" if picked.startswith("z") else "bash"
                prefs["shell"] = self._selected_shell
                self._save_preferences(context.home, prefs)

        filename = ".zshrc" if self._selected_shell == "zsh" else ".bashrc"
        return context.home / filename

    def _backup_file(self, path: Path) -> None:
        if not path.exists():
            return

        backup = Path(f"{path}.bak")
        shutil.copy2(path, backup)

    def _upsert_managed_path_block(self, original_text: str, cleaned_entries: list[str]) -> str:
        export_line = f'export PATH="{":".join(cleaned_entries)}"'
        block = "\n".join([self._path_block_start, export_line, self._path_block_end])

        start = original_text.find(self._path_block_start)
        end = original_text.find(self._path_block_end)
        if start != -1 and end != -1 and end > start:
            end_index = end + len(self._path_block_end)
            return f"{original_text[:start]}{block}{original_text[end_index:]}"

        prefix = original_text
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        return f"{prefix}\n{block}\n"

    def _prefs_path(self, home: Path) -> Path:
        return home / self._prefs_filename

    def _load_preferences(self, home: Path) -> dict[str, Any]:
        path = self._prefs_path(home)
        if not path.exists():
            return {}

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_preferences(self, home: Path, prefs: dict[str, Any]) -> None:
        path = self._prefs_path(home)
        path.write_text(json.dumps(prefs, indent=2, sort_keys=True), encoding="utf-8")