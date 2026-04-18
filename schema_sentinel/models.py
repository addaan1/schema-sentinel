from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {
            Severity.LOW: 1,
            Severity.MEDIUM: 2,
            Severity.HIGH: 3,
            Severity.CRITICAL: 4,
        }[self]

    @property
    def title(self) -> str:
        return self.value.capitalize()


@dataclass(frozen=True)
class NumericSummary:
    mean: float | None = None
    std: float | None = None
    median: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    p05: float | None = None
    p95: float | None = None


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    semantic_type: str
    pandas_dtype: str
    row_count: int
    non_null_count: int
    null_count: int
    null_rate: float
    unique_count: int
    unique_ratio: float
    is_constant: bool
    sample_values: tuple[str, ...] = ()
    distinct_values: tuple[str, ...] = ()
    top_values: tuple[tuple[str, int], ...] = ()
    numeric_summary: NumericSummary | None = None


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    title: str
    message: str
    affected_columns: tuple[str, ...] = ()
    old_value: str | None = None
    new_value: str | None = None
    recommendation: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ColumnMatch:
    old_column: str
    new_column: str
    confidence: float
    name_similarity: float
    profile_similarity: float
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    old_path: Path
    new_path: Path
    old_rows: int
    new_rows: int
    old_columns: int
    new_columns: int
    added_columns: list[str]
    removed_columns: list[str]
    shared_columns: list[str]
    rename_suggestions: list[ColumnMatch]
    old_profiles: dict[str, ColumnProfile]
    new_profiles: dict[str, ColumnProfile]
    findings: list[Finding]
    recommendations: list[str]
    overall_risk: Severity
    fail_on: Severity
    exit_code: int
    stability_score: int
    output_dir: Path | None = None
    output_files: dict[str, Path] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
