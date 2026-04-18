from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import DriftConfig
from .models import ColumnProfile, Finding, NumericSummary, Severity
from .utils import (
    clean_numeric_text,
    format_delta_percent,
    format_number,
    format_percent,
    normalize_text,
    top_value_pairs,
    unique_preserving_order,
)

BOOLEAN_VALUES = {"true", "false", "yes", "no", "y", "n", "1", "0", "t", "f"}


@dataclass(frozen=True)
class ColumnComparison:
    column: str
    severity: Severity
    notes: tuple[str, ...]


def _string_series(series: pd.Series) -> pd.Series:
    return series.dropna().astype(str).map(normalize_text)


def _numeric_series(series: pd.Series) -> pd.Series:
    cleaned = _string_series(series).map(clean_numeric_text)
    numeric = pd.to_numeric(cleaned, errors="coerce")
    return numeric.dropna().astype(float)


def _boolean_ratio(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    normalized = values.str.lower()
    matches = normalized.isin(BOOLEAN_VALUES).sum()
    return matches / len(values)


def _numeric_ratio(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    cleaned = values.map(clean_numeric_text)
    numeric = pd.to_numeric(cleaned, errors="coerce")
    return numeric.notna().sum() / len(values)


def infer_semantic_type(series: pd.Series) -> str:
    values = _string_series(series)
    if values.empty:
        return "empty"

    numeric_ratio = _numeric_ratio(values)
    if numeric_ratio >= 0.95:
        return "numeric"

    boolean_ratio = _boolean_ratio(values)
    if boolean_ratio >= 0.95:
        return "boolean"

    unique_count = int(values.nunique(dropna=True))
    unique_ratio = unique_count / len(values) if len(values) else 0.0
    if unique_count <= 20 and unique_ratio <= 0.8:
        return "categorical"

    return "text"


def _numeric_summary(series: pd.Series) -> NumericSummary | None:
    values = _numeric_series(series)
    if values.empty:
        return None

    return NumericSummary(
        mean=float(values.mean()),
        std=float(values.std(ddof=0)) if len(values) > 1 else 0.0,
        median=float(values.median()),
        minimum=float(values.min()),
        maximum=float(values.max()),
        p05=float(values.quantile(0.05)),
        p95=float(values.quantile(0.95)),
    )


def profile_column(name: str, series: pd.Series) -> ColumnProfile:
    values = series.dropna()
    cleaned = _string_series(series)
    row_count = int(len(series))
    non_null_count = int(len(values))
    null_count = row_count - non_null_count
    null_rate = null_count / row_count if row_count else 0.0
    unique_count = int(cleaned.nunique(dropna=True))
    unique_ratio = unique_count / non_null_count if non_null_count else 0.0
    semantic_type = infer_semantic_type(series)
    is_constant = non_null_count > 0 and unique_count == 1
    sample_values = tuple(unique_preserving_order(cleaned.tolist(), limit=5))
    distinct_values = tuple(unique_preserving_order(cleaned.tolist(), limit=50))
    top_values = top_value_pairs(cleaned, limit=5)
    numeric_summary = _numeric_summary(series) if semantic_type == "numeric" else None

    return ColumnProfile(
        name=name,
        semantic_type=semantic_type,
        pandas_dtype=str(series.dtype),
        row_count=row_count,
        non_null_count=non_null_count,
        null_count=null_count,
        null_rate=null_rate,
        unique_count=unique_count,
        unique_ratio=unique_ratio,
        is_constant=is_constant,
        sample_values=sample_values,
        distinct_values=distinct_values,
        top_values=top_values,
        numeric_summary=numeric_summary,
    )


def analyze_dataframe(frame: pd.DataFrame) -> dict[str, ColumnProfile]:
    return {column: profile_column(column, frame[column]) for column in frame.columns}


def _severity_from_ratio(delta: float, *, low: float, medium: float, high: float) -> Severity | None:
    absolute = abs(delta)
    if absolute >= high:
        return Severity.HIGH
    if absolute >= medium:
        return Severity.MEDIUM
    if absolute >= low:
        return Severity.LOW
    return None


def _column_label(old: ColumnProfile, new: ColumnProfile, column_label: str | None = None) -> str:
    if column_label:
        return column_label
    if old.name == new.name:
        return old.name
    return f"{old.name} -> {new.name}"


def _affected_columns(old: ColumnProfile, new: ColumnProfile) -> tuple[str, ...]:
    if old.name == new.name:
        return (old.name,)
    return (old.name, new.name)


def compare_row_counts(old_rows: int, new_rows: int, *, thresholds: DriftConfig | None = None) -> Finding | None:
    if old_rows == new_rows:
        return None

    config = thresholds or DriftConfig()
    delta = new_rows - old_rows
    ratio = abs(delta) / max(old_rows, 1)
    severity = (
        _severity_from_ratio(ratio, low=config.row_low, medium=config.row_medium, high=config.row_high)
        or Severity.LOW
    )
    direction = "increased" if delta > 0 else "decreased"

    return Finding(
        code="row_count_change",
        severity=severity,
        title="Row count changed",
        message=(
            f"Row count {direction} from {format_number(old_rows)} to {format_number(new_rows)} "
            f"({format_delta_percent(delta / max(old_rows, 1))})."
        ),
        old_value=str(old_rows),
        new_value=str(new_rows),
        recommendation="Confirm the new dataset size is expected before trusting downstream metrics.",
        details={"relative_change": ratio, "difference": delta},
    )


def compare_type_change(old: ColumnProfile, new: ColumnProfile, *, column_label: str | None = None) -> Finding | None:
    if old.semantic_type == new.semantic_type:
        return None

    if {old.semantic_type, new.semantic_type} <= {"categorical", "text"}:
        severity = Severity.MEDIUM
    elif "empty" in {old.semantic_type, new.semantic_type}:
        severity = Severity.HIGH
    elif "boolean" in {old.semantic_type, new.semantic_type} and "categorical" in {
        old.semantic_type,
        new.semantic_type,
    }:
        severity = Severity.MEDIUM
    else:
        severity = Severity.HIGH

    label = _column_label(old, new, column_label)
    return Finding(
        code="type_change",
        severity=severity,
        title=f"Type changed for `{label}`",
        message=(
            f"Column `{label}` changed from {old.semantic_type} to {new.semantic_type}. "
            f"Old examples: {', '.join(old.sample_values[:3]) or '-'}; "
            f"new examples: {', '.join(new.sample_values[:3]) or '-'}."
        ),
        affected_columns=_affected_columns(old, new),
        old_value=old.semantic_type,
        new_value=new.semantic_type,
        recommendation="Validate the upstream source and make sure downstream code can handle the new shape.",
        details={"old_dtype": old.pandas_dtype, "new_dtype": new.pandas_dtype},
    )


def compare_null_rate(
    old: ColumnProfile,
    new: ColumnProfile,
    *,
    thresholds: DriftConfig | None = None,
    column_label: str | None = None,
) -> Finding | None:
    config = thresholds or DriftConfig()
    delta = new.null_rate - old.null_rate
    if delta <= config.null_rate_low:
        return None

    severity = (
        _severity_from_ratio(
            delta,
            low=config.null_rate_low,
            medium=config.null_rate_medium,
            high=config.null_rate_high,
        )
        or Severity.LOW
    )
    label = _column_label(old, new, column_label)
    return Finding(
        code="null_rate_increase",
        severity=severity,
        title=f"Null rate increased in `{label}`",
        message=(
            f"Null rate rose from {format_percent(old.null_rate)} to {format_percent(new.null_rate)} "
            f"({format_delta_percent(delta)})."
        ),
        affected_columns=_affected_columns(old, new),
        old_value=format_percent(old.null_rate),
        new_value=format_percent(new.null_rate),
        recommendation="Check whether missing values were introduced upstream or during file generation.",
        details={"delta": delta},
    )


def compare_unique_ratio(
    old: ColumnProfile,
    new: ColumnProfile,
    *,
    thresholds: DriftConfig | None = None,
    column_label: str | None = None,
) -> Finding | None:
    config = thresholds or DriftConfig()
    delta = new.unique_ratio - old.unique_ratio
    absolute = abs(delta)
    if absolute < config.unique_ratio_low:
        return None

    severity = Severity.MEDIUM if absolute >= config.unique_ratio_medium else Severity.LOW
    label = _column_label(old, new, column_label)
    return Finding(
        code="unique_ratio_change",
        severity=severity,
        title=f"Unique ratio changed in `{label}`",
        message=(
            f"Unique ratio moved from {format_percent(old.unique_ratio)} to {format_percent(new.unique_ratio)} "
            f"({format_delta_percent(delta)})."
        ),
        affected_columns=_affected_columns(old, new),
        old_value=format_percent(old.unique_ratio),
        new_value=format_percent(new.unique_ratio),
        recommendation="Review whether the column became more ID-like, more repetitive, or lost variety.",
        details={"delta": delta},
    )


def compare_constant_state(
    old: ColumnProfile,
    new: ColumnProfile,
    *,
    column_label: str | None = None,
) -> Finding | None:
    if old.is_constant == new.is_constant:
        return None

    label = _column_label(old, new, column_label)
    if new.is_constant and not old.is_constant:
        return Finding(
            code="constant_column",
            severity=Severity.MEDIUM,
            title=f"`{label}` became constant",
            message=(
                f"Column `{label}` is now constant with value "
                f"`{new.sample_values[0] if new.sample_values else '-'}`."
            ),
            affected_columns=_affected_columns(old, new),
            recommendation="Confirm that the field is not accidentally frozen or truncated upstream.",
        )
    return None


def compare_category_drift(
    old: ColumnProfile,
    new: ColumnProfile,
    *,
    column_label: str | None = None,
) -> Finding | None:
    if old.semantic_type not in {"categorical", "text", "boolean"}:
        return None
    if new.semantic_type not in {"categorical", "text", "boolean"}:
        return None

    old_values = {normalize_text(value) for value in old.distinct_values or old.sample_values}
    new_values = {normalize_text(value) for value in new.distinct_values or new.sample_values}
    if not old_values or not new_values:
        return None

    old_values.update({normalize_text(value) for value, _ in old.top_values})
    new_values.update({normalize_text(value) for value, _ in new.top_values})

    intersection = old_values & new_values
    union = old_values | new_values
    if not union:
        return None

    unseen_values = sorted(new_values - old_values)
    removed_values = sorted(old_values - new_values)
    unseen_ratio = len(unseen_values) / len(new_values) if new_values else 0.0
    removed_ratio = len(removed_values) / len(old_values) if old_values else 0.0
    jaccard = len(intersection) / len(union)

    if unseen_ratio < 0.1 and removed_ratio < 0.1:
        return None

    if unseen_ratio >= 0.4 or removed_ratio >= 0.4 or jaccard < 0.4:
        severity = Severity.HIGH
    elif unseen_ratio >= 0.2 or removed_ratio >= 0.2 or jaccard < 0.7:
        severity = Severity.MEDIUM
    else:
        severity = Severity.LOW

    label = _column_label(old, new, column_label)
    preview_new = ", ".join(unseen_values[:3]) or "-"
    preview_old = ", ".join(removed_values[:3]) or "-"

    return Finding(
        code="category_drift",
        severity=severity,
        title=f"Category drift detected in `{label}`",
        message=(
            f"Observed {len(unseen_values)} new category values and {len(removed_values)} removed values. "
            f"New examples: {preview_new}. Removed examples: {preview_old}."
        ),
        affected_columns=_affected_columns(old, new),
        recommendation="Review allowed values and decide whether the new categories should be accepted.",
        details={
            "unseen_ratio": unseen_ratio,
            "removed_ratio": removed_ratio,
            "jaccard": jaccard,
        },
    )


def compare_numeric_drift(
    old: ColumnProfile,
    new: ColumnProfile,
    *,
    thresholds: DriftConfig | None = None,
    column_label: str | None = None,
) -> Finding | None:
    if old.semantic_type != "numeric" or new.semantic_type != "numeric":
        return None
    if old.numeric_summary is None or new.numeric_summary is None:
        return None

    config = thresholds or DriftConfig()
    pairs = {
        "mean": (old.numeric_summary.mean, new.numeric_summary.mean),
        "median": (old.numeric_summary.median, new.numeric_summary.median),
        "std": (old.numeric_summary.std, new.numeric_summary.std),
        "p95": (old.numeric_summary.p95, new.numeric_summary.p95),
        "minimum": (old.numeric_summary.minimum, new.numeric_summary.minimum),
        "maximum": (old.numeric_summary.maximum, new.numeric_summary.maximum),
    }

    def _shift(a: float | None, b: float | None) -> float:
        if a is None or b is None:
            return 0.0
        return abs(b - a) / max(abs(a), abs(b), 1.0)

    shifts = {name: _shift(old_value, new_value) for name, (old_value, new_value) in pairs.items()}
    composite = (
        shifts["mean"] * 0.35
        + shifts["median"] * 0.2
        + shifts["std"] * 0.2
        + shifts["p95"] * 0.15
        + max(shifts["minimum"], shifts["maximum"]) * 0.1
    )

    if composite < config.numeric_composite_medium:
        return None

    severity = Severity.HIGH if composite >= config.numeric_composite_high or shifts["mean"] >= 0.3 else Severity.MEDIUM
    direction = "up" if (new.numeric_summary.mean or 0) >= (old.numeric_summary.mean or 0) else "down"
    top_direction = "higher" if direction == "up" else "lower"
    label = _column_label(old, new, column_label)

    return Finding(
        code="numeric_drift",
        severity=severity,
        title=f"Numeric drift detected in `{label}`",
        message=(
            f"Mean moved from {format_number(old.numeric_summary.mean)} to {format_number(new.numeric_summary.mean)} "
            f"and the {top_direction} tail shifted as well."
        ),
        affected_columns=_affected_columns(old, new),
        recommendation="Check whether this shift is expected before retraining models or updating dashboards.",
        details={
            "composite": composite,
            "mean_shift": shifts["mean"],
            "median_shift": shifts["median"],
            "std_shift": shifts["std"],
            "p95_shift": shifts["p95"],
        },
    )


def compare_column_profiles(
    old: ColumnProfile,
    new: ColumnProfile,
    *,
    thresholds: DriftConfig | None = None,
    column_label: str | None = None,
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    if column_label is not None:
        label = column_label
    elif old.name == new.name:
        label = old.name
    else:
        label = f"{old.name} -> {new.name}"

    for finding in (
        compare_type_change(old, new, column_label=label),
        compare_null_rate(old, new, thresholds=thresholds, column_label=label),
        compare_unique_ratio(old, new, thresholds=thresholds, column_label=label),
        compare_constant_state(old, new, column_label=label),
        compare_category_drift(old, new, column_label=label),
        compare_numeric_drift(old, new, thresholds=thresholds, column_label=label),
    ):
        if finding is not None:
            findings.append(finding)

    return tuple(findings)


def aggregate_column_notes(findings: list[Finding], column: str) -> tuple[Severity, tuple[str, ...]]:
    relevant = [finding for finding in findings if column in finding.affected_columns]
    if not relevant:
        return Severity.LOW, ()

    severity = max(relevant, key=lambda finding: finding.severity.rank).severity
    notes = tuple(
        unique_preserving_order([finding.title for finding in relevant] + [finding.message for finding in relevant])
    )
    return severity, notes
