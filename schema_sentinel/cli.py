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
from .contract import load_contract
from .errors import ContractError, DatasetReadError, SchemaSentinelError
from .models import Severity
from .report import write_github_step_summary
from .risk import severity_label
from .utils import format_number, format_percent
from .validate import initialize_contract, validate_and_write

console = Console()

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
)
contract_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(contract_app, name="contract")


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
    title = "Top breaches" if result.mode == "validate" else "Top findings"
    table = Table(title=title, show_lines=False, expand=True)
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
    if result.mode == "validate":
        table.add_row("Contract rows", format_number(result.old_rows))
        table.add_row("Observed rows", format_number(result.new_rows))
        table.add_row("Expected columns", format_number(result.old_columns))
        table.add_row("Observed columns", format_number(result.new_columns))
        table.add_row("Unexpected columns", format_number(len(result.added_columns)))
        table.add_row("Missing required columns", format_number(len(result.removed_columns)))
    else:
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
    if result.mode == "validate":
        contract_name = result.contract_path.name if result.contract_path else "schema-contract.json"
        subject_line = (
            f"Validating [cyan]{result.new_path.name}[/cyan] against [cyan]{contract_name}[/cyan]"
        )
    else:
        subject_line = (
            f"Comparing [cyan]{result.old_path.name}[/cyan] -> [cyan]{result.new_path.name}[/cyan]"
        )
    header = Panel.fit(
        f"[bold]Schema Sentinel[/bold]\n"
        f"{subject_line}\n\n"
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
        message = "No contract breaches detected." if result.mode == "validate" else "No high-risk drift detected."
        console.print(Panel(message, border_style="green"))

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
    write_github_step_summary(result)
    raise typer.Exit(code=result.exit_code)


@app.command("validate")
def validate(
    candidate: Annotated[Path, typer.Argument(help="Path to the CSV file to validate.")],
    contract: Annotated[
        Path,
        typer.Option(
            "--contract",
            help="Path to the committed schema contract JSON file.",
        ),
    ],
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            help="Path to a JSON config file. Defaults to ./config.json when present.",
        ),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Directory where reports will be written."),
    ] = None,
    format: Annotated[
        ReportFormat | None,
        typer.Option("--format", "-f", case_sensitive=False, help="Which report format to write."),
    ] = None,
    fail_on: Annotated[
        Severity | None,
        typer.Option(
            "--fail-on",
            case_sensitive=False,
            help="Override the contract failure severity threshold for this run.",
        ),
    ] = None,
) -> None:
    try:
        app_config = load_config(config)
        selected_formats = format.value if format is not None else app_config.output.formats
        resolved_formats = normalize_report_formats(selected_formats)
        resolved_output_dir = output_dir or app_config.output.directory

        # Validate early so the CLI can fail fast with a contract-specific error.
        loaded_contract = load_contract(contract)
        resolved_fail_on = fail_on or loaded_contract.fail_on

        result = validate_and_write(
            candidate,
            contract_path=contract,
            output_dir=resolved_output_dir,
            formats=resolved_formats,
            fail_on=resolved_fail_on,
        )
    except (DatasetReadError, ContractError, SchemaSentinelError) as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc

    _render_terminal_report(result)
    write_github_step_summary(result)
    raise typer.Exit(code=result.exit_code)


@contract_app.command("init")
def contract_init(
    baseline: Annotated[Path, typer.Argument(help="Path to the baseline CSV file.")],
    out: Annotated[
        Path,
        typer.Option("--out", help="Where the generated schema contract should be written."),
    ] = Path("schema-contract.json"),
    fail_on: Annotated[
        Severity,
        typer.Option(
            "--fail-on",
            case_sensitive=False,
            help="Default failure severity embedded into the generated contract.",
        ),
    ] = Severity.HIGH,
) -> None:
    try:
        written = initialize_contract(baseline, out_path=out, fail_on=fail_on)
    except (DatasetReadError, ContractError, SchemaSentinelError) as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc

    console.print(
        Panel.fit(
            f"[bold]Schema contract created[/bold]\n"
            f"Baseline: [cyan]{baseline.name}[/cyan]\n"
            f"Output: [cyan]{written}[/cyan]",
            title="Contract",
            border_style="green",
        )
    )


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
