from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import pandas as pd

from .errors import DatasetReadError
from .models import Finding, Severity

MISSING_TOKENS = {"", "na", "n/a", "null", "none", "nan", "nil"}

SEVERITY_BY_RANK = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise DatasetReadError(f"Could not find dataset: {path}")

    try:
        frame = pd.read_csv(
            path,
            dtype=str,
            encoding="utf-8-sig",
            keep_default_na=True,
            na_values=list(MISSING_TOKENS),
        )
    except pd.errors.EmptyDataError as exc:
        raise DatasetReadError(f"Dataset is empty or missing a header row: {path}") from exc
    except pd.errors.ParserError as exc:
        raise DatasetReadError(f"Could not parse CSV file: {path}") from exc
    except UnicodeDecodeError as exc:
        raise DatasetReadError(f"Could not read file encoding for: {path}") from exc
    except Exception as exc:  # pragma: no cover - safety net for unexpected IO issues
        raise DatasetReadError(f"Unexpected error while reading {path}: {exc}") from exc

    if frame.shape[1] == 0:
        raise DatasetReadError(f"CSV file has no columns: {path}")
    if frame.shape[0] == 0:
        raise DatasetReadError(f"CSV file has no data rows to compare: {path}")

    return frame


def format_percent(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.{digits}f}%"


def format_delta_percent(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.{digits}f}%"


def format_number(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if float(value).is_integer():
        return f"{int(value):,}"
    text = f"{float(value):,.{digits}f}"
    return text.rstrip("0").rstrip(".")


def format_ratio(value: float | None) -> str:
    return format_percent(value)


def format_change(old: float | int | None, new: float | int | None) -> str:
    if old is None or new is None:
        return "-"
    return f"{format_number(old)} -> {format_number(new)}"


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def clean_numeric_text(value: str) -> str:
    return value.replace(",", "").replace("$", "").replace("%", "")


def unique_preserving_order(values: Iterable[str], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
        if limit is not None and len(output) >= limit:
            break
    return output


def top_value_pairs(series: pd.Series, limit: int = 5) -> tuple[tuple[str, int], ...]:
    counts = series.value_counts(dropna=True).head(limit)
    return tuple((str(index), int(count)) for index, count in counts.items())


def sort_findings(findings: Sequence[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda item: (
            -SEVERITY_BY_RANK[item.severity],
            item.code,
            ",".join(item.affected_columns),
            item.title,
        ),
    )


def highest_severity(findings: Sequence[Finding]) -> Severity:
    if not findings:
        return Severity.LOW
    return max(findings, key=lambda finding: finding.severity.rank).severity


def severity_counts(findings: Sequence[Finding]) -> dict[Severity, int]:
    counts = {severity: 0 for severity in Severity}
    for finding in findings:
        counts[finding.severity] += 1
    return counts


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def make_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def escape_markdown(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")
