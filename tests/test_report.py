from __future__ import annotations

from pathlib import Path

from schema_sentinel.compare import compare_datasets
from schema_sentinel.report import render_html_report, render_markdown_report

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_render_markdown_report_contains_required_sections() -> None:
    result = compare_datasets(PROJECT_ROOT / "examples" / "old.csv", PROJECT_ROOT / "examples" / "new.csv")

    markdown = render_markdown_report(result)

    assert "# Schema Sentinel Report" in markdown
    assert "## Overview" in markdown
    assert "## Severity Summary" in markdown
    assert "## Rename Suggestions" in markdown
    assert "## Column Changes" in markdown
    assert "## Recommendations" in markdown
    assert "## Output" in markdown


def test_render_html_report_contains_required_sections() -> None:
    result = compare_datasets(PROJECT_ROOT / "examples" / "old.csv", PROJECT_ROOT / "examples" / "new.csv")

    html = render_html_report(result)

    assert "Schema Sentinel Report" in html
    assert "Summary at a glance" in html
    assert "Findings by severity" in html
    assert "Rename suggestions" in html
    assert "Column-level diff" in html
    assert "Recommendations" in html
