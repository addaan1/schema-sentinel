from __future__ import annotations

from pathlib import Path

from schema_sentinel.compare import compare_datasets
from schema_sentinel.contract import build_contract, write_contract
from schema_sentinel.report import render_html_report, render_json_report, render_markdown_report
from schema_sentinel.validate import validate_dataset

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


def test_render_json_report_includes_contract_fields_for_validate_mode(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.csv"
    baseline.write_text("id,score\n1,10\n2,20\n", encoding="utf-8")
    contract_path = tmp_path / "schema-contract.json"
    write_contract(build_contract(baseline), contract_path)

    result = validate_dataset(baseline, contract_path=contract_path)
    report_json = render_json_report(result)

    assert '"mode": "validate"' in report_json
    assert '"schema_version": "0.3"' in report_json
    assert '"contract_path"' in report_json
    assert '"breaches": []' in report_json


def test_render_markdown_report_mentions_contract_in_validate_mode(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.csv"
    baseline.write_text("id,score\n1,10\n2,20\n", encoding="utf-8")
    contract_path = tmp_path / "schema-contract.json"
    write_contract(build_contract(baseline), contract_path)

    markdown = render_markdown_report(validate_dataset(baseline, contract_path=contract_path))

    assert "| Mode | `validate` |" in markdown
    assert "| Contract | `schema-contract.json` |" in markdown
