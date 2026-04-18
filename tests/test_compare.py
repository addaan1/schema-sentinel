from __future__ import annotations

from pathlib import Path

import pytest

from schema_sentinel.compare import compare_and_write, compare_datasets
from schema_sentinel.errors import DatasetReadError
from schema_sentinel.models import Severity

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_compare_datasets_on_project_examples_detects_major_drift() -> None:
    result = compare_datasets(PROJECT_ROOT / "examples" / "old.csv", PROJECT_ROOT / "examples" / "new.csv")

    assert result.overall_risk == Severity.CRITICAL
    assert result.exit_code == 2
    assert result.added_columns == ["segment"]
    assert result.removed_columns == ["active"]
    assert result.rename_suggestions == []
    assert any(finding.code == "removed_column" for finding in result.findings)
    assert any(finding.code == "numeric_drift" for finding in result.findings)
    assert any(finding.code == "category_drift" for finding in result.findings)


def test_compare_and_write_creates_report_files(tmp_path: Path) -> None:
    result = compare_and_write(
        PROJECT_ROOT / "examples" / "old.csv",
        PROJECT_ROOT / "examples" / "new.csv",
        output_dir=tmp_path / "outputs",
        formats=("all",),
    )

    assert result.output_files["markdown"].exists()
    assert result.output_files["html"].exists()
    assert result.output_files["json"].exists()
    assert "Schema Sentinel Report" in result.output_files["markdown"].read_text(encoding="utf-8")
    assert "Schema Sentinel Report" in result.output_files["html"].read_text(encoding="utf-8")
    assert "\"rename_suggestions\"" in result.output_files["json"].read_text(encoding="utf-8")


def test_compare_datasets_detects_column_rename(tmp_path: Path) -> None:
    old_file = tmp_path / "old.csv"
    new_file = tmp_path / "new.csv"
    old_file.write_text("id,active,score\n1,true,10\n2,false,11\n", encoding="utf-8")
    new_file.write_text("id,is_active,score\n1,true,10\n2,false,11\n", encoding="utf-8")

    result = compare_datasets(old_file, new_file)

    assert result.removed_columns == []
    assert result.added_columns == []
    assert len(result.rename_suggestions) == 1
    rename = result.rename_suggestions[0]
    assert rename.old_column == "active"
    assert rename.new_column == "is_active"
    assert any(finding.code == "rename_suggestion" for finding in result.findings)


def test_compare_datasets_no_shared_columns_returns_critical(tmp_path: Path) -> None:
    old_file = tmp_path / "old.csv"
    new_file = tmp_path / "new.csv"
    old_file.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    new_file.write_text("c,d\n5,6\n7,8\n", encoding="utf-8")

    result = compare_datasets(old_file, new_file)

    assert result.overall_risk == Severity.CRITICAL
    assert result.exit_code == 2
    assert any(finding.code == "no_shared_columns" for finding in result.findings)


def test_compare_datasets_missing_file_raises_dataset_error(tmp_path: Path) -> None:
    existing = tmp_path / "existing.csv"
    existing.write_text("a\n1\n", encoding="utf-8")

    with pytest.raises(DatasetReadError):
        compare_datasets(tmp_path / "missing.csv", existing)


def test_compare_datasets_empty_file_raises_dataset_error(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("", encoding="utf-8")
    other = tmp_path / "other.csv"
    other.write_text("a\n1\n", encoding="utf-8")

    with pytest.raises(DatasetReadError):
        compare_datasets(empty_file, other)
