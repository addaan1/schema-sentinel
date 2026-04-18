from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from schema_sentinel.cli import app
from schema_sentinel.contract import build_contract, write_contract

PROJECT_ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


def test_cli_exits_zero_for_identical_datasets(tmp_path: Path) -> None:
    old_file = tmp_path / "old.csv"
    new_file = tmp_path / "new.csv"
    content = "id,value\n1,alpha\n2,beta\n3,gamma\n"
    old_file.write_text(content, encoding="utf-8")
    new_file.write_text(content, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "compare",
            str(old_file),
            str(new_file),
            "--output-dir",
            str(tmp_path / "outputs"),
        ],
    )

    assert result.exit_code == 0
    assert "Overall risk: SAFE" in result.output
    assert (tmp_path / "outputs" / "summary.md").exists()
    assert (tmp_path / "outputs" / "report.html").exists()
    assert (tmp_path / "outputs" / "report.json").exists()


def test_cli_exits_one_for_medium_drift(tmp_path: Path) -> None:
    old_file = tmp_path / "old.csv"
    new_file = tmp_path / "new.csv"
    old_file.write_text("id,score\n1,10\n2,11\n3,12\n4,13\n5,14\n", encoding="utf-8")
    new_file.write_text("id,score\n1,10\n2,\n3,12\n4,13\n5,14\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "compare",
            str(old_file),
            str(new_file),
            "--output-dir",
            str(tmp_path / "outputs"),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 1
    assert "Overall risk" in result.output
    assert (tmp_path / "outputs" / "report.json").exists()
    assert not (tmp_path / "outputs" / "summary.md").exists()
    assert not (tmp_path / "outputs" / "report.html").exists()


def test_cli_exits_two_for_critical_drift(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "compare",
            str(PROJECT_ROOT / "examples" / "old.csv"),
            str(PROJECT_ROOT / "examples" / "new.csv"),
            "--output-dir",
            str(tmp_path / "outputs"),
        ],
    )

    assert result.exit_code == 2
    assert "Overall risk" in result.output
    assert (tmp_path / "outputs" / "summary.md").exists()
    assert (tmp_path / "outputs" / "report.html").exists()
    assert (tmp_path / "outputs" / "report.json").exists()


def test_contract_init_command_writes_contract_file(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.csv"
    baseline.write_text("id,plan\n1,free\n2,pro\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["contract", "init", str(baseline), "--out", str(tmp_path / "schema-contract.json")],
    )

    assert result.exit_code == 0
    assert (tmp_path / "schema-contract.json").exists()
    payload = json.loads((tmp_path / "schema-contract.json").read_text(encoding="utf-8"))
    assert payload["columns"]["plan"]["required"] is True


def test_validate_command_writes_reports_and_step_summary(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.csv"
    baseline.write_text("id,plan,score\n1,free,10\n2,pro,20\n", encoding="utf-8")
    contract_path = tmp_path / "schema-contract.json"
    write_contract(build_contract(baseline), contract_path)
    step_summary = tmp_path / "step-summary.md"

    result = runner.invoke(
        app,
        [
            "validate",
            str(baseline),
            "--contract",
            str(contract_path),
            "--output-dir",
            str(tmp_path / "outputs"),
        ],
        env={"GITHUB_STEP_SUMMARY": str(step_summary)},
    )

    assert result.exit_code == 0
    assert "Validating" in result.output
    assert (tmp_path / "outputs" / "summary.md").exists()
    assert (tmp_path / "outputs" / "report.html").exists()
    assert (tmp_path / "outputs" / "report.json").exists()
    assert step_summary.exists()
    assert "Mode: `validate`" in step_summary.read_text(encoding="utf-8")
