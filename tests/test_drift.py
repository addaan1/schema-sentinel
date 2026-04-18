from __future__ import annotations

import pandas as pd
import pytest

from schema_sentinel.drift import compare_column_profiles, infer_semantic_type, profile_column
from schema_sentinel.models import Severity


def test_infer_semantic_type_and_profile_numeric() -> None:
    series = pd.Series(["1", "2", None, "3"])

    assert infer_semantic_type(series) == "numeric"

    profile = profile_column("score", series)
    assert profile.null_rate == pytest.approx(0.25)
    assert profile.semantic_type == "numeric"
    assert profile.numeric_summary is not None
    assert profile.numeric_summary.mean == pytest.approx(2.0)


def test_type_change_detects_numeric_to_text() -> None:
    old_profile = profile_column("value", pd.Series(["1", "2", "3", "4"]))
    new_profile = profile_column("value", pd.Series(["alpha", "beta", "gamma", "delta"]))

    findings = compare_column_profiles(old_profile, new_profile)

    type_change = next(finding for finding in findings if finding.code == "type_change")
    assert type_change.severity == Severity.HIGH
    assert "numeric" in type_change.message
    assert "text" in type_change.message


def test_category_drift_detects_new_values() -> None:
    old_profile = profile_column("plan", pd.Series(["free", "free", "pro", "pro", "enterprise"]))
    new_profile = profile_column(
        "plan",
        pd.Series(["free", "enterprise", "enterprise", "business", "business", "vip"]),
    )

    findings = compare_column_profiles(old_profile, new_profile)

    category_finding = next(finding for finding in findings if finding.code == "category_drift")
    assert category_finding.severity in {Severity.MEDIUM, Severity.HIGH}
    assert "new category" in category_finding.message.lower() or "observed" in category_finding.message.lower()


def test_numeric_drift_detects_shift() -> None:
    old_profile = profile_column("revenue", pd.Series(["100", "110", "120", "130", "140"]))
    new_profile = profile_column("revenue", pd.Series(["180", "190", "200", "210", "220"]))

    findings = compare_column_profiles(old_profile, new_profile)

    drift_finding = next(finding for finding in findings if finding.code == "numeric_drift")
    assert drift_finding.severity in {Severity.MEDIUM, Severity.HIGH}
    assert "Mean moved" in drift_finding.message
