from __future__ import annotations

import json
from pathlib import Path

from schema_sentinel.contract import build_contract, load_contract, write_contract
from schema_sentinel.models import Severity


def test_build_contract_is_deterministic(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.csv"
    baseline.write_text("id,plan,score\n1,free,10\n2,pro,20\n3,pro,30\n", encoding="utf-8")

    contract_a = build_contract(baseline, fail_on=Severity.HIGH)
    contract_b = build_contract(baseline, fail_on=Severity.HIGH)
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"

    write_contract(contract_a, out_a)
    write_contract(contract_b, out_b)

    assert out_a.read_text(encoding="utf-8") == out_b.read_text(encoding="utf-8")


def test_generated_contract_contains_editable_policy_fields(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.csv"
    baseline.write_text("id,plan,score\n1,free,10\n2,pro,20\n3,pro,30\n", encoding="utf-8")

    contract = build_contract(baseline, fail_on=Severity.MEDIUM)
    out_path = tmp_path / "schema-contract.json"
    write_contract(contract, out_path)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert payload["fail_on"] == "medium"
    assert payload["dataset"]["row_count"]["baseline"] == 3
    assert payload["dataset"]["strict_columns"] is False
    assert payload["columns"]["score"]["required"] is True
    assert payload["columns"]["score"]["baseline_profile"]["semantic_type"] == "numeric"
    assert payload["columns"]["plan"]["category_drift"]["max_new_ratio"] == 0.2


def test_load_contract_round_trips_generated_contract(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.csv"
    baseline.write_text("id,plan\n1,free\n2,pro\n", encoding="utf-8")

    written = tmp_path / "schema-contract.json"
    write_contract(build_contract(baseline), written)
    contract = load_contract(written)

    assert contract.path == written
    assert contract.fail_on == Severity.HIGH
    assert "plan" in contract.columns
    assert contract.columns["plan"].baseline_profile.name == "plan"
    assert contract.columns["plan"].semantic_type == contract.columns["plan"].baseline_profile.semantic_type
