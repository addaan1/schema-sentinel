from __future__ import annotations

from schema_sentinel.models import Finding, Severity
from schema_sentinel.risk import (
    build_recommendations,
    calculate_stability_score,
    exit_code_for,
    overall_severity,
)


def test_exit_code_mapping_respects_threshold() -> None:
    medium = Finding(code="null_rate_increase", severity=Severity.MEDIUM, title="Nulls", message="...")
    high = Finding(code="numeric_drift", severity=Severity.HIGH, title="Drift", message="...")
    critical = Finding(code="removed_column", severity=Severity.CRITICAL, title="Removed", message="...")

    assert exit_code_for([], Severity.HIGH) == 0
    assert exit_code_for([medium], Severity.HIGH) == 1
    assert exit_code_for([high], Severity.HIGH) == 2
    assert exit_code_for([critical], Severity.HIGH) == 2


def test_overall_severity_and_score() -> None:
    findings = [
        Finding(code="added_column", severity=Severity.LOW, title="Added", message="..."),
        Finding(code="category_drift", severity=Severity.MEDIUM, title="Category", message="..."),
        Finding(code="removed_column", severity=Severity.CRITICAL, title="Removed", message="..."),
    ]

    assert overall_severity(findings) == Severity.CRITICAL
    assert calculate_stability_score(findings) < 100


def test_recommendations_are_deduplicated() -> None:
    findings = [
        Finding(
            code="numeric_drift",
            severity=Severity.HIGH,
            title="Drift A",
            message="...",
            recommendation="Review the shifted metric.",
        ),
        Finding(
            code="numeric_drift",
            severity=Severity.HIGH,
            title="Drift B",
            message="...",
            recommendation="Review the shifted metric.",
        ),
    ]

    recommendations = build_recommendations(findings)
    assert recommendations == ["Review the shifted metric."]
