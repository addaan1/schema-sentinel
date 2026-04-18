from __future__ import annotations

from .models import Finding, Severity
from .utils import highest_severity, severity_counts

BASE_PENALTIES = {
    "no_shared_columns": 45,
    "removed_column": 30,
    "rename_suggestion": 6,
    "type_change": 22,
    "null_rate_increase": 14,
    "numeric_drift": 12,
    "category_drift": 10,
    "unique_ratio_change": 8,
    "row_count_change": 6,
    "constant_column": 8,
    "added_column": 4,
}

SEVERITY_PENALTIES = {
    Severity.LOW: 3,
    Severity.MEDIUM: 10,
    Severity.HIGH: 20,
    Severity.CRITICAL: 35,
}


def severity_label(severity: Severity | None, findings: list[Finding]) -> str:
    if not findings:
        return "SAFE"
    if severity is None:
        return "SAFE"
    return severity.value.upper()


def calculate_stability_score(findings: list[Finding]) -> int:
    if not findings:
        return 100

    penalty = 0
    for finding in findings:
        penalty += BASE_PENALTIES.get(finding.code, SEVERITY_PENALTIES[finding.severity])
    return max(0, 100 - penalty)


def overall_severity(findings: list[Finding]) -> Severity:
    return highest_severity(findings)


def exit_code_for(findings: list[Finding], fail_on: Severity) -> int:
    if not findings:
        return 0

    severity = overall_severity(findings)
    if severity.rank >= fail_on.rank or severity == Severity.CRITICAL:
        return 2
    return 1


def build_recommendations(findings: list[Finding]) -> list[str]:
    suggestions: list[str] = []
    seen: set[str] = set()

    if not findings:
        return ["No high-risk drift detected. The dataset looks safe to use."]

    ordered = sorted(findings, key=lambda item: (-item.severity.rank, item.code))
    for finding in ordered:
        if finding.recommendation and finding.recommendation not in seen:
            seen.add(finding.recommendation)
            suggestions.append(finding.recommendation)

    if not suggestions:
        suggestions.append("Review the changed columns before using the new dataset downstream.")

    return suggestions[:4]


def summarize_findings(findings: list[Finding]) -> dict[str, int]:
    counts = severity_counts(findings)
    return {
        "total": len(findings),
        "low": counts[Severity.LOW],
        "medium": counts[Severity.MEDIUM],
        "high": counts[Severity.HIGH],
        "critical": counts[Severity.CRITICAL],
    }


def is_failure(findings: list[Finding], fail_on: Severity) -> bool:
    if not findings:
        return False
    return overall_severity(findings).rank >= fail_on.rank
