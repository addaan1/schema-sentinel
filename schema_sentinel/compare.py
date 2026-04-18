from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import DriftConfig, MatchingConfig
from .drift import (
    analyze_dataframe,
    compare_column_profiles,
    compare_row_counts,
)
from .matching import match_renamed_columns
from .models import ComparisonResult, Finding, Severity
from .risk import build_recommendations, calculate_stability_score, exit_code_for, overall_severity
from .utils import load_csv, sort_findings


def compare_frames(
    old_frame: pd.DataFrame,
    new_frame: pd.DataFrame,
    *,
    old_path: Path,
    new_path: Path,
    fail_on: Severity = Severity.HIGH,
    matching_config: MatchingConfig | None = None,
    drift_config: DriftConfig | None = None,
) -> ComparisonResult:
    old_profiles = analyze_dataframe(old_frame)
    new_profiles = analyze_dataframe(new_frame)

    old_columns = list(old_frame.columns)
    new_columns = list(new_frame.columns)
    shared_columns = [column for column in old_columns if column in new_columns]
    added_candidates = [column for column in new_columns if column not in old_columns]
    removed_candidates = [column for column in old_columns if column not in new_columns]

    rename_suggestions = match_renamed_columns(
        old_profiles,
        new_profiles,
        removed_candidates,
        added_candidates,
        matching=matching_config,
    )

    renamed_old = {suggestion.old_column for suggestion in rename_suggestions}
    renamed_new = {suggestion.new_column for suggestion in rename_suggestions}
    added_columns = [column for column in added_candidates if column not in renamed_new]
    removed_columns = [column for column in removed_candidates if column not in renamed_old]

    findings: list[Finding] = []

    row_change = compare_row_counts(len(old_frame), len(new_frame), thresholds=drift_config)
    if row_change is not None:
        findings.append(row_change)

    for column in removed_columns:
        findings.append(
            Finding(
                code="removed_column",
                severity=Severity.CRITICAL,
                title=f"Removed column `{column}`",
                message=f"Column `{column}` exists in the old dataset but not in the new one.",
                affected_columns=(column,),
                old_value="present",
                new_value="missing",
                recommendation=(
                    "Restore the removed column or confirm every downstream consumer can handle its removal."
                ),
            )
        )

    for column in added_columns:
        findings.append(
            Finding(
                code="added_column",
                severity=Severity.LOW,
                title=f"Added column `{column}`",
                message=f"Column `{column}` appears only in the new dataset.",
                affected_columns=(column,),
                old_value="missing",
                new_value="present",
                recommendation="Document the new column so downstream consumers know whether to use it.",
            )
        )

    for suggestion in rename_suggestions:
        findings.append(
            Finding(
                code="rename_suggestion",
                severity=Severity.LOW,
                title=f"Likely rename: `{suggestion.old_column}` -> `{suggestion.new_column}`",
                message=(
                    f"Column `{suggestion.old_column}` appears to have been renamed to "
                    f"`{suggestion.new_column}` with confidence {suggestion.confidence:.0%}."
                ),
                affected_columns=(suggestion.old_column, suggestion.new_column),
                old_value=suggestion.old_column,
                new_value=suggestion.new_column,
                recommendation=(
                    "Confirm the rename and update downstream mappings, documentation, and tests."
                ),
                details={
                    "confidence": suggestion.confidence,
                    "name_similarity": suggestion.name_similarity,
                    "profile_similarity": suggestion.profile_similarity,
                    **suggestion.details,
                },
            )
        )

    if not shared_columns and not rename_suggestions:
        findings.append(
            Finding(
                code="no_shared_columns",
                severity=Severity.CRITICAL,
                title="No shared columns found",
                message=(
                    "The old and new datasets do not share any column names, so schema comparison "
                    "cannot detect deeper drift patterns."
                ),
                recommendation="Double-check that you selected the intended pair of datasets.",
            )
        )

    for column in shared_columns:
        findings.extend(
            compare_column_profiles(
                old_profiles[column],
                new_profiles[column],
                thresholds=drift_config,
            )
        )

    for suggestion in rename_suggestions:
        findings.extend(
            compare_column_profiles(
                old_profiles[suggestion.old_column],
                new_profiles[suggestion.new_column],
                thresholds=drift_config,
                column_label=f"{suggestion.old_column} -> {suggestion.new_column}",
            )
        )

    findings = sort_findings(findings)
    overall = overall_severity(findings)
    recommendations = build_recommendations(findings)
    exit_code = exit_code_for(findings, fail_on=fail_on)
    stability_score = calculate_stability_score(findings)

    result = ComparisonResult(
        old_path=old_path,
        new_path=new_path,
        old_rows=len(old_frame),
        new_rows=len(new_frame),
        old_columns=len(old_columns),
        new_columns=len(new_columns),
        added_columns=added_columns,
        removed_columns=removed_columns,
        shared_columns=shared_columns,
        rename_suggestions=rename_suggestions,
        old_profiles=old_profiles,
        new_profiles=new_profiles,
        findings=findings,
        recommendations=recommendations,
        overall_risk=overall,
        fail_on=fail_on,
        exit_code=exit_code,
        stability_score=stability_score,
    )

    return result


def compare_datasets(
    old_path: Path,
    new_path: Path,
    *,
    fail_on: Severity = Severity.HIGH,
    matching_config: MatchingConfig | None = None,
    drift_config: DriftConfig | None = None,
) -> ComparisonResult:
    old_frame = load_csv(old_path)
    new_frame = load_csv(new_path)
    return compare_frames(
        old_frame,
        new_frame,
        old_path=old_path,
        new_path=new_path,
        fail_on=fail_on,
        matching_config=matching_config,
        drift_config=drift_config,
    )


def compare_and_write(
    old_path: Path,
    new_path: Path,
    *,
    output_dir: Path,
    formats: tuple[str, ...],
    fail_on: Severity = Severity.HIGH,
    matching_config: MatchingConfig | None = None,
    drift_config: DriftConfig | None = None,
) -> ComparisonResult:
    from .report import write_reports

    result = compare_datasets(
        old_path,
        new_path,
        fail_on=fail_on,
        matching_config=matching_config,
        drift_config=drift_config,
    )
    result.output_dir = output_dir
    result.output_files = write_reports(result, output_dir=output_dir, formats=formats)
    return result
