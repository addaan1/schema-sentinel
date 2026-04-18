from __future__ import annotations

from pathlib import Path

import pandas as pd

from .contract import (
    CategoryDriftPolicy,
    NumericDriftPolicy,
    SchemaContract,
    build_contract,
    load_contract,
    write_contract,
)
from .drift import analyze_dataframe
from .models import ColumnProfile, ComparisonResult, Finding, Severity
from .risk import build_recommendations, calculate_stability_score, exit_code_for, overall_severity
from .utils import format_number, format_percent, load_csv, normalize_text, sort_findings


def initialize_contract(
    baseline_path: Path,
    *,
    out_path: Path,
    fail_on: Severity = Severity.HIGH,
) -> Path:
    contract = build_contract(baseline_path, fail_on=fail_on)
    return write_contract(contract, out_path)


def _row_count_finding(contract: SchemaContract, candidate_rows: int) -> Finding | None:
    minimum = contract.row_count.minimum
    maximum = contract.row_count.maximum
    if minimum <= candidate_rows <= maximum:
        return None

    baseline = contract.row_count.baseline
    delta = abs(candidate_rows - baseline) / max(baseline, 1)
    severity = Severity.HIGH if delta >= 0.25 else Severity.MEDIUM
    return Finding(
        code="row_count_contract_breach",
        severity=severity,
        title="Row count is outside the contract range",
        message=(
            f"Observed {format_number(candidate_rows)} rows, but the contract allows "
            f"{format_number(minimum)} to {format_number(maximum)} rows."
        ),
        old_value=f"{minimum}-{maximum}",
        new_value=str(candidate_rows),
        recommendation="Review whether the dataset size change is expected before promoting this snapshot.",
        details={"baseline": baseline, "minimum": minimum, "maximum": maximum},
    )


def _missing_required_column_finding(column: str) -> Finding:
    return Finding(
        code="missing_required_column",
        severity=Severity.CRITICAL,
        title=f"Missing required column `{column}`",
        message=f"Column `{column}` is required by the contract but is not present in the dataset.",
        affected_columns=(column,),
        old_value="required",
        new_value="missing",
        recommendation="Restore the missing column or update the committed contract if the removal is intentional.",
    )


def _unexpected_column_finding(column: str, *, strict_columns: bool) -> Finding:
    severity = Severity.HIGH if strict_columns else Severity.LOW
    message = (
        f"Column `{column}` is not defined in the contract."
        if strict_columns
        else f"Column `{column}` is not defined in the contract, but extra columns are currently allowed."
    )
    recommendation = (
        "Either remove the extra column or update the contract before merging."
        if strict_columns
        else "Decide whether the new column should be added to the contract."
    )
    return Finding(
        code="unexpected_column",
        severity=severity,
        title=f"Unexpected column `{column}`",
        message=message,
        affected_columns=(column,),
        old_value="contract-missing",
        new_value="present",
        recommendation=recommendation,
        details={"strict_columns": strict_columns},
    )


def _type_mismatch_finding(expected: ColumnProfile, observed: ColumnProfile) -> Finding | None:
    if expected.semantic_type == observed.semantic_type:
        return None
    return Finding(
        code="contract_type_mismatch",
        severity=Severity.HIGH,
        title=f"Type mismatch for `{expected.name}`",
        message=(
            f"Contract expects `{expected.name}` to be {expected.semantic_type}, "
            f"but the dataset looks like {observed.semantic_type}."
        ),
        affected_columns=(expected.name,),
        old_value=expected.semantic_type,
        new_value=observed.semantic_type,
        recommendation="Validate the upstream producer and update the contract only if this new type is intentional.",
    )


def _null_rate_breach_finding(
    column: str,
    *,
    nullable: bool,
    observed_null_rate: float,
    allowed_null_rate: float,
) -> Finding | None:
    if not nullable and observed_null_rate > 0:
        severity = Severity.HIGH
    else:
        delta = observed_null_rate - allowed_null_rate
        if delta <= 0:
            return None
        severity = Severity.HIGH if delta >= 0.10 else Severity.MEDIUM

    return Finding(
        code="contract_null_rate_breach",
        severity=severity,
        title=f"Null rate breached in `{column}`",
        message=(
            f"Observed null rate {format_percent(observed_null_rate)} exceeds the contract limit "
            f"of {format_percent(allowed_null_rate)}."
        ),
        affected_columns=(column,),
        old_value=format_percent(allowed_null_rate),
        new_value=format_percent(observed_null_rate),
        recommendation="Check whether missing values were introduced upstream or relax the contract deliberately.",
    )


def _unique_ratio_breach_finding(
    column: str,
    *,
    observed_unique_ratio: float,
    minimum: float | None,
    maximum: float | None,
) -> Finding | None:
    if minimum is not None and observed_unique_ratio < minimum:
        delta = minimum - observed_unique_ratio
        severity = Severity.MEDIUM if delta >= 0.15 else Severity.LOW
        return Finding(
            code="contract_unique_ratio_breach",
            severity=severity,
            title=f"Unique ratio fell below the contract in `{column}`",
            message=(
                f"Observed unique ratio {format_percent(observed_unique_ratio)} is below the contract minimum "
                f"of {format_percent(minimum)}."
            ),
            affected_columns=(column,),
            old_value=format_percent(minimum),
            new_value=format_percent(observed_unique_ratio),
            recommendation="Review whether the column lost variety or became more repetitive than expected.",
        )

    if maximum is not None and observed_unique_ratio > maximum:
        delta = observed_unique_ratio - maximum
        severity = Severity.MEDIUM if delta >= 0.15 else Severity.LOW
        return Finding(
            code="contract_unique_ratio_breach",
            severity=severity,
            title=f"Unique ratio exceeded the contract in `{column}`",
            message=(
                f"Observed unique ratio {format_percent(observed_unique_ratio)} is above the contract maximum "
                f"of {format_percent(maximum)}."
            ),
            affected_columns=(column,),
            old_value=format_percent(maximum),
            new_value=format_percent(observed_unique_ratio),
            recommendation="Review whether the column became more ID-like or more fragmented than expected.",
        )

    return None


def _numeric_composite(old: ColumnProfile, new: ColumnProfile) -> float:
    if old.numeric_summary is None or new.numeric_summary is None:
        return 0.0

    pairs = {
        "mean": (old.numeric_summary.mean, new.numeric_summary.mean),
        "median": (old.numeric_summary.median, new.numeric_summary.median),
        "std": (old.numeric_summary.std, new.numeric_summary.std),
        "p95": (old.numeric_summary.p95, new.numeric_summary.p95),
        "minimum": (old.numeric_summary.minimum, new.numeric_summary.minimum),
        "maximum": (old.numeric_summary.maximum, new.numeric_summary.maximum),
    }

    def _shift(left: float | None, right: float | None) -> float:
        if left is None or right is None:
            return 0.0
        return abs(right - left) / max(abs(left), abs(right), 1.0)

    shifts = {name: _shift(left, right) for name, (left, right) in pairs.items()}
    return (
        shifts["mean"] * 0.35
        + shifts["median"] * 0.20
        + shifts["std"] * 0.20
        + shifts["p95"] * 0.15
        + max(shifts["minimum"], shifts["maximum"]) * 0.10
    )


def _numeric_drift_breach_finding(
    baseline: ColumnProfile,
    observed: ColumnProfile,
    policy: NumericDriftPolicy | None,
) -> Finding | None:
    if baseline.semantic_type != "numeric" or observed.semantic_type != "numeric":
        return None
    if policy is None:
        return None

    composite = _numeric_composite(baseline, observed)
    if composite < policy.warn:
        return None

    severity = Severity.HIGH if composite >= policy.fail else Severity.MEDIUM
    return Finding(
        code="contract_numeric_drift",
        severity=severity,
        title=f"Numeric drift breached in `{baseline.name}`",
        message=(
            f"Numeric drift composite for `{baseline.name}` reached {composite:.2f}, "
            f"above the contract threshold of {policy.warn:.2f}."
        ),
        affected_columns=(baseline.name,),
        old_value=f"{policy.warn:.2f}",
        new_value=f"{composite:.2f}",
        recommendation="Review whether the numeric distribution changed for a valid business reason.",
        details={"composite": composite, "warn": policy.warn, "fail": policy.fail},
    )


def _category_drift_ratios(baseline: ColumnProfile, observed: ColumnProfile) -> tuple[float, float]:
    baseline_values = {normalize_text(value) for value in baseline.distinct_values or baseline.sample_values}
    observed_values = {normalize_text(value) for value in observed.distinct_values or observed.sample_values}
    baseline_values.update({normalize_text(value) for value, _ in baseline.top_values})
    observed_values.update({normalize_text(value) for value, _ in observed.top_values})
    baseline_values.discard("")
    observed_values.discard("")

    if not baseline_values or not observed_values:
        return 0.0, 0.0

    new_ratio = len(observed_values - baseline_values) / len(observed_values)
    removed_ratio = len(baseline_values - observed_values) / len(baseline_values)
    return new_ratio, removed_ratio


def _category_drift_breach_finding(
    baseline: ColumnProfile,
    observed: ColumnProfile,
    policy: CategoryDriftPolicy | None,
) -> Finding | None:
    if policy is None:
        return None

    new_ratio, removed_ratio = _category_drift_ratios(baseline, observed)
    if new_ratio <= policy.max_new_ratio and removed_ratio <= policy.max_removed_ratio:
        return None

    excess = max(new_ratio - policy.max_new_ratio, removed_ratio - policy.max_removed_ratio)
    severity = Severity.HIGH if excess >= 0.20 else Severity.MEDIUM
    return Finding(
        code="contract_category_drift",
        severity=severity,
        title=f"Category drift breached in `{baseline.name}`",
        message=(
            f"Observed new-category ratio {format_percent(new_ratio)} and removed-category ratio "
            f"{format_percent(removed_ratio)} exceed the contract limits."
        ),
        affected_columns=(baseline.name,),
        old_value=(
            f"new<={format_percent(policy.max_new_ratio)}, removed<={format_percent(policy.max_removed_ratio)}"
        ),
        new_value=f"new={format_percent(new_ratio)}, removed={format_percent(removed_ratio)}",
        recommendation="Review whether new categorical values should be accepted into the contract.",
        details={
            "new_ratio": new_ratio,
            "removed_ratio": removed_ratio,
            "max_new_ratio": policy.max_new_ratio,
            "max_removed_ratio": policy.max_removed_ratio,
        },
    )


def validate_frame(
    candidate_frame: pd.DataFrame,
    *,
    candidate_path: Path,
    contract: SchemaContract,
    fail_on: Severity | None = None,
) -> ComparisonResult:
    candidate_profiles = analyze_dataframe(candidate_frame)

    findings: list[Finding] = []
    findings_from_contract: list[Finding] = []
    baseline_profiles: dict[str, ColumnProfile] = {}

    row_count_finding = _row_count_finding(contract, len(candidate_frame))
    if row_count_finding is not None:
        findings.append(row_count_finding)

    expected_columns = {
        name: column
        for name, column in contract.columns.items()
        if not column.ignore
    }
    expected_names = set(expected_columns)
    candidate_names = set(candidate_frame.columns)

    unexpected_columns = sorted(candidate_names - set(contract.columns))
    for column in unexpected_columns:
        finding = _unexpected_column_finding(column, strict_columns=contract.strict_columns)
        findings.append(finding)
        findings_from_contract.append(finding)

    missing_required = sorted(
        name
        for name, column in expected_columns.items()
        if column.required and name not in candidate_names
    )
    for column in missing_required:
        finding = _missing_required_column_finding(column)
        findings.append(finding)
        findings_from_contract.append(finding)

    shared_columns = sorted(expected_names & candidate_names)
    for name in shared_columns:
        contract_column = expected_columns[name]
        baseline_profile = contract_column.baseline_profile
        observed_profile = candidate_profiles[name]
        baseline_profiles[name] = baseline_profile

        for finding in (
            _type_mismatch_finding(baseline_profile, observed_profile),
            _null_rate_breach_finding(
                name,
                nullable=contract_column.nullable,
                observed_null_rate=observed_profile.null_rate,
                allowed_null_rate=contract_column.null_rate_max,
            ),
            _unique_ratio_breach_finding(
                name,
                observed_unique_ratio=observed_profile.unique_ratio,
                minimum=contract_column.unique_ratio_min,
                maximum=contract_column.unique_ratio_max,
            ),
            _numeric_drift_breach_finding(baseline_profile, observed_profile, contract_column.numeric_drift),
            _category_drift_breach_finding(baseline_profile, observed_profile, contract_column.category_drift),
        ):
            if finding is not None:
                findings.append(finding)
                findings_from_contract.append(finding)

    findings = sort_findings(findings)
    contract_findings = sort_findings(findings_from_contract)
    resolved_fail_on = fail_on or contract.fail_on
    overall = overall_severity(findings)
    baseline_name = contract.generated_from.get("file_name")
    if not isinstance(baseline_name, str) or not baseline_name:
        baseline_name = contract.path.name if contract.path else "baseline.csv"
    result = ComparisonResult(
        old_path=Path(baseline_name),
        new_path=candidate_path,
        old_rows=contract.row_count.baseline,
        new_rows=len(candidate_frame),
        old_columns=len(expected_columns),
        new_columns=len(candidate_frame.columns),
        added_columns=unexpected_columns,
        removed_columns=missing_required,
        shared_columns=shared_columns,
        rename_suggestions=[],
        old_profiles=baseline_profiles,
        new_profiles={name: candidate_profiles[name] for name in shared_columns},
        findings=findings,
        recommendations=build_recommendations(findings),
        overall_risk=overall,
        fail_on=resolved_fail_on,
        exit_code=exit_code_for(findings, resolved_fail_on),
        stability_score=calculate_stability_score(findings),
        mode="validate",
        contract_path=contract.path,
        contract_breaches=contract_findings,
        contract_metadata={
            "version": contract.version,
            "generated_from": contract.generated_from,
            "strict_columns": contract.strict_columns,
            "row_count": {
                "baseline": contract.row_count.baseline,
                "minimum": contract.row_count.minimum,
                "maximum": contract.row_count.maximum,
            },
        },
    )
    return result


def validate_dataset(
    candidate_path: Path,
    *,
    contract_path: Path,
    fail_on: Severity | None = None,
) -> ComparisonResult:
    contract = load_contract(contract_path)
    candidate_frame = load_csv(candidate_path)
    return validate_frame(candidate_frame, candidate_path=candidate_path, contract=contract, fail_on=fail_on)


def validate_and_write(
    candidate_path: Path,
    *,
    contract_path: Path,
    output_dir: Path,
    formats: tuple[str, ...],
    fail_on: Severity | None = None,
) -> ComparisonResult:
    from .report import write_reports

    result = validate_dataset(candidate_path, contract_path=contract_path, fail_on=fail_on)
    result.output_dir = output_dir
    result.output_files = write_reports(result, output_dir=output_dir, formats=formats)
    return result
