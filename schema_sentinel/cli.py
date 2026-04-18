from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .compare import compare_and_write
from .config import load_config, normalize_report_formats
from .errors import DatasetReadError, SchemaSentinelError
from .models import Severity
from .risk import severity_label
from .utils import format_number, format_percent

console = Console()

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Schema Sentinel command group."""


class ReportFormat(StrEnum):
    markdown = "markdown"
    html = "html"
    json = "json"
    both = "both"
    all = "all"


def _severity_style(severity: Severity) -> str:
    return {
        Severity.LOW: "cyan",
        Severity.MEDIUM: "yellow",
        Severity.HIGH: "dark_orange",
        Severity.CRITICAL: "bold red",
    }[severity]


def _findings_table(result) -> Table:
    table = Table(title="Top findings", show_lines=False, expand=True)
    table.add_column("Severity", style="bold", no_wrap=True)
    table.add_column("Code", style="dim", no_wrap=True)
    table.add_column("Issue", overflow="fold")
    table.add_column("Columns", overflow="fold")

    for finding in result.findings[:6]:
        table.add_row(
            finding.severity.title,
            finding.code,
            finding.title,
            ", ".join(finding.affected_columns) if finding.affected_columns else "-",
        )
    return table


def _rename_table(result) -> Table:
    table = Table(title="Rename suggestions", show_lines=False, expand=True)
    table.add_column("Old column", style="bold")
    table.add_column("New column", style="bold")
    table.add_column("Confidence")
    table.add_column("Reason", overflow="fold")

    for suggestion in result.rename_suggestions[:6]:
        table.add_row(
            suggestion.old_column,
            suggestion.new_column,
            format_percent(suggestion.confidence),
            suggestion.reason,
        )
    return table


def _summary_table(result) -> Table:
    table = Table(title="Comparison summary", show_lines=False, expand=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Old rows", format_number(result.old_rows))
    table.add_row("New rows", format_number(result.new_rows))
    table.add_row("Old columns", format_number(result.old_columns))
    table.add_row("New columns", format_number(result.new_columns))
    table.add_row("Added columns", format_number(len(result.added_columns)))
    table.add_row("Removed columns", format_number(len(result.removed_columns)))
    table.add_row("Rename suggestions", format_number(len(result.rename_suggestions)))
    table.add_row("Shared columns", format_number(len(result.shared_columns)))
    table.add_row("Findings", format_number(len(result.findings)))
    table.add_row("Stability score", f"{result.stability_score}/100")
    return table


def _output_table(result) -> Table:
    table = Table(title="Output files", show_lines=False, expand=True)
    table.add_column("Format", style="bold")
    table.add_column("Path")
    if result.output_files:
        for name, path in result.output_files.items():
            table.add_row(name, str(path))
    else:
        table.add_row("none", "No report files were written")
    return table


def _render_terminal_report(result) -> None:
    overall_label = severity_label(result.overall_risk, result.findings)
    risk_style = _severity_style(result.overall_risk)
    overall_markup = f"[{risk_style}]{overall_label}[/{risk_style}]"
    header = Panel.fit(
        f"[bold]Schema Sentinel[/bold]\n"
        f"Comparing [cyan]{result.old_path.name}[/cyan] -> [cyan]{result.new_path.name}[/cyan]\n\n"
        f"Overall risk: {overall_markup}\n"
        f"Stability score: [bold]{result.stability_score}/100[/bold]",
        title="Report",
        border_style=risk_style,
    )
    console.print(header)
    console.print(_summary_table(result))

    if result.rename_suggestions:
        console.print(_rename_table(result))

    if result.findings:
        console.print(_findings_table(result))
    else:
        console.print(Panel("No high-risk drift detected.", border_style="green"))

    if result.recommendations:
        console.print(
            Panel(
                "\n".join(f"- {recommendation}" for recommendation in result.recommendations),
                title="Recommendations",
                border_style="blue",
            )
        )

    if result.output_files:
        console.print(_output_table(result))


@app.command("compare")
def compare(
    old: Annotated[Path, typer.Argument(help="Path to the old CSV file.")],
    new: Annotated[Path, typer.Argument(help="Path to the new CSV file.")],
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            help="Path to a JSON config file. Defaults to ./config.json when present.",
        ),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            "-o",
            help="Directory where reports will be written.",
        ),
    ] = None,
    format: Annotated[
        ReportFormat | None,
        typer.Option(
            "--format",
            "-f",
            case_sensitive=False,
            help="Which report format to write.",
        ),
    ] = None,
    fail_on: Annotated[
        Severity | None,
        typer.Option(
            "--fail-on",
            case_sensitive=False,
            help="Return exit code 2 when the overall risk is at or above this severity.",
        ),
    ] = None,
) -> None:
    try:
        app_config = load_config(config)
        selected_formats = format.value if format is not None else app_config.output.formats
        resolved_formats = normalize_report_formats(selected_formats)
        resolved_output_dir = output_dir or app_config.output.directory
        resolved_fail_on = fail_on or app_config.output.fail_on

        result = compare_and_write(
            old,
            new,
            output_dir=resolved_output_dir,
            formats=resolved_formats,
            fail_on=resolved_fail_on,
            matching_config=app_config.matching,
            drift_config=app_config.drift,
        )
    except DatasetReadError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc
    except SchemaSentinelError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc

    _render_terminal_report(result)
    raise typer.Exit(code=result.exit_code)


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
