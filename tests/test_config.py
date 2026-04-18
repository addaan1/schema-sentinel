from __future__ import annotations

import json
from pathlib import Path

import pytest

from schema_sentinel.config import AppConfig, load_config, normalize_report_formats
from schema_sentinel.models import Severity


def test_load_config_uses_defaults_when_file_is_missing(tmp_path: Path) -> None:
    config = load_config(cwd=tmp_path)

    assert isinstance(config, AppConfig)
    assert config.output.directory == Path("outputs")
    assert config.output.formats == ("markdown", "html")
    assert config.output.fail_on == Severity.HIGH
    assert config.matching.rename_threshold == pytest.approx(0.78)


def test_load_config_reads_json_and_normalizes_formats(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "output": {
                    "directory": "artifacts",
                    "formats": ["json", "markdown"],
                    "fail_on": "medium",
                },
                "matching": {
                    "rename_threshold": 0.9,
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.output.directory == tmp_path / "artifacts"
    assert config.output.formats == ("json", "markdown")
    assert config.output.fail_on == Severity.MEDIUM
    assert config.matching.rename_threshold == pytest.approx(0.9)


def test_normalize_report_formats_supports_aliases() -> None:
    assert normalize_report_formats("both") == ("markdown", "html")
    assert normalize_report_formats("all") == ("markdown", "html", "json")
    assert normalize_report_formats(["markdown", "json"]) == ("markdown", "json")
