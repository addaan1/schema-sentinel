from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from schema_sentinel.cli import app

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
