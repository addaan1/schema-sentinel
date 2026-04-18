from __future__ import annotations

import json
from pathlib import Path

from schema_sentinel.contract import build_contract, write_contract
from schema_sentinel.models import Severity
from schema_sentinel.validate import validate_dataset


def test_validate_dataset_identical_to_contract_is_safe(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.csv"
    baseline.write_text("id,plan,score\n1,free,10\n2,pro,20\n3,pro,30\n", encoding="utf-8")
    contract_path = tmp_path / "schema-contract.json"
    write_contract(build_contract(baseline), contract_path)

    result = validate_dataset(baseline, contract_path=contract_path)

    assert result.mode == "validate"
    assert result.contract_path == contract_path
    assert result.exit_code == 0
    assert result.findings == []
    assert result.contract_breaches == []


def test_validate_dataset_detects_missing_required_and_unexpected_columns(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.csv"
    baseline.write_text("id,score\n1,10\n2,20\n", encoding="utf-8")
    contract_path = tmp_path / "schema-contract.json"
    write_contract(build_contract(baseline), contract_path)

    candidate = tmp_path / "candidate.csv"
    candidate.write_text("id,segment\n1,retail\n2,enterprise\n", encoding="utf-8")

    result = validate_dataset(candidate, contract_path=contract_path)

    assert result.overall_risk == Severity.CRITICAL
    assert result.exit_code == 2
    assert result.added_columns == ["segment"]
    assert result.removed_columns == ["score"]
    assert any(finding.code == "missing_required_column" for finding in result.findings)
    assert any(finding.code == "unexpected_column" for finding in result.findings)


def test_validate_dataset_detects_type_and_null_breaches(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.csv"
    baseline.write_text("id,score\n1,10\n2,20\n3,30\n", encoding="utf-8")
    contract_path = tmp_path / "schema-contract.json"
    write_contract(build_contract(baseline), contract_path)

    candidate = tmp_path / "candidate.csv"
    candidate.write_text("id,score\n1,ten\n2,\n3,thirty\n", encoding="utf-8")

    result = validate_dataset(candidate, contract_path=contract_path)

    assert result.exit_code == 2
    assert any(finding.code == "contract_type_mismatch" for finding in result.findings)
    assert any(finding.code == "contract_null_rate_breach" for finding in result.findings)


def test_validate_dataset_respects_ignore_and_optional_columns(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.csv"
    baseline.write_text("id,score,notes\n1,10,ok\n2,20,ok\n", encoding="utf-8")
    contract_path = tmp_path / "schema-contract.json"
    write_contract(build_contract(baseline), contract_path)

    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    payload["columns"]["notes"]["ignore"] = True
    payload["columns"]["score"]["required"] = False
    contract_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    candidate = tmp_path / "candidate.csv"
    candidate.write_text("id\n1\n2\n", encoding="utf-8")

    result = validate_dataset(candidate, contract_path=contract_path)

    assert result.exit_code == 0
    assert result.removed_columns == []
    assert not any(finding.code == "missing_required_column" for finding in result.findings)
