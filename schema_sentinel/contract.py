from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__
from .config import DriftConfig
from .drift import analyze_dataframe
from .errors import ContractError
from .models import ColumnProfile, NumericSummary, Severity
from .utils import clamp, load_csv

CONTRACT_VERSION = "1"


@dataclass(frozen=True)
class RowCountContract:
    baseline: int
    minimum: int
    maximum: int


@dataclass(frozen=True)
class NumericDriftPolicy:
    warn: float
    fail: float


@dataclass(frozen=True)
class CategoryDriftPolicy:
    max_new_ratio: float
    max_removed_ratio: float


@dataclass(frozen=True)
class ColumnContract:
    required: bool
    ignore: bool
    semantic_type: str
    nullable: bool
    null_rate_max: float
    unique_ratio_min: float | None
    unique_ratio_max: float | None
    numeric_drift: NumericDriftPolicy | None
    category_drift: CategoryDriftPolicy | None
    baseline_profile: ColumnProfile


@dataclass(frozen=True)
class SchemaContract:
    version: str
    generated_from: dict[str, Any]
    fail_on: Severity
    strict_columns: bool
    row_count: RowCountContract
    columns: dict[str, ColumnContract]
    path: Path | None = None


def _profile_to_dict(profile: ColumnProfile) -> dict[str, Any]:
    numeric_summary = None
    if profile.numeric_summary is not None:
        numeric_summary = {
            "mean": profile.numeric_summary.mean,
            "std": profile.numeric_summary.std,
            "median": profile.numeric_summary.median,
            "minimum": profile.numeric_summary.minimum,
            "maximum": profile.numeric_summary.maximum,
            "p05": profile.numeric_summary.p05,
            "p95": profile.numeric_summary.p95,
        }

    return {
        "name": profile.name,
        "semantic_type": profile.semantic_type,
        "pandas_dtype": profile.pandas_dtype,
        "row_count": profile.row_count,
        "non_null_count": profile.non_null_count,
        "null_count": profile.null_count,
        "null_rate": profile.null_rate,
        "unique_count": profile.unique_count,
        "unique_ratio": profile.unique_ratio,
        "is_constant": profile.is_constant,
        "sample_values": list(profile.sample_values),
        "distinct_values": list(profile.distinct_values),
        "top_values": [[value, count] for value, count in profile.top_values],
        "numeric_summary": numeric_summary,
    }


def _profile_from_dict(data: dict[str, Any]) -> ColumnProfile:
    numeric_summary_raw = data.get("numeric_summary")
    numeric_summary = None
    if isinstance(numeric_summary_raw, dict):
        numeric_summary = NumericSummary(
            mean=_optional_float(numeric_summary_raw.get("mean")),
            std=_optional_float(numeric_summary_raw.get("std")),
            median=_optional_float(numeric_summary_raw.get("median")),
            minimum=_optional_float(numeric_summary_raw.get("minimum")),
            maximum=_optional_float(numeric_summary_raw.get("maximum")),
            p05=_optional_float(numeric_summary_raw.get("p05")),
            p95=_optional_float(numeric_summary_raw.get("p95")),
        )

    top_values_raw = data.get("top_values", [])
    top_values = tuple((str(value), int(count)) for value, count in top_values_raw)

    return ColumnProfile(
        name=str(data.get("name", "")),
        semantic_type=str(data.get("semantic_type", "text")),
        pandas_dtype=str(data.get("pandas_dtype", "object")),
        row_count=int(data.get("row_count", 0)),
        non_null_count=int(data.get("non_null_count", 0)),
        null_count=int(data.get("null_count", 0)),
        null_rate=float(data.get("null_rate", 0.0)),
        unique_count=int(data.get("unique_count", 0)),
        unique_ratio=float(data.get("unique_ratio", 0.0)),
        is_constant=bool(data.get("is_constant", False)),
        sample_values=tuple(str(value) for value in data.get("sample_values", [])),
        distinct_values=tuple(str(value) for value in data.get("distinct_values", [])),
        top_values=top_values,
        numeric_summary=numeric_summary,
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _default_row_contract(row_count: int) -> RowCountContract:
    if row_count <= 20:
        ratio = 0.20
    elif row_count <= 100:
        ratio = 0.10
    else:
        ratio = 0.05

    tolerance = max(1, int(round(row_count * ratio)))
    return RowCountContract(
        baseline=row_count,
        minimum=max(0, row_count - tolerance),
        maximum=row_count + tolerance,
    )


def _default_unique_bounds(profile: ColumnProfile) -> tuple[float | None, float | None]:
    if profile.semantic_type not in {"categorical", "boolean"}:
        return None, None

    margin = max(0.05, min(0.20, profile.unique_ratio * 0.30))
    return (
        clamp(profile.unique_ratio - margin, 0.0, 1.0),
        clamp(profile.unique_ratio + margin, 0.0, 1.0),
    )


def _default_null_rate_max(profile: ColumnProfile) -> float:
    if profile.null_rate <= 0:
        return 0.0
    return clamp(max(profile.null_rate + 0.05, profile.null_rate * 1.35), 0.0, 1.0)


def _build_column_contract(profile: ColumnProfile, drift_config: DriftConfig) -> ColumnContract:
    unique_ratio_min, unique_ratio_max = _default_unique_bounds(profile)

    numeric_drift = None
    if profile.semantic_type == "numeric":
        numeric_drift = NumericDriftPolicy(
            warn=drift_config.numeric_composite_medium,
            fail=drift_config.numeric_composite_high,
        )

    category_drift = None
    if profile.semantic_type in {"categorical", "boolean"}:
        category_drift = CategoryDriftPolicy(max_new_ratio=0.20, max_removed_ratio=0.20)

    return ColumnContract(
        required=True,
        ignore=False,
        semantic_type=profile.semantic_type,
        nullable=profile.null_rate > 0,
        null_rate_max=_default_null_rate_max(profile),
        unique_ratio_min=unique_ratio_min,
        unique_ratio_max=unique_ratio_max,
        numeric_drift=numeric_drift,
        category_drift=category_drift,
        baseline_profile=profile,
    )


def build_contract(
    baseline_path: Path,
    *,
    frame: pd.DataFrame | None = None,
    fail_on: Severity = Severity.HIGH,
    drift_config: DriftConfig | None = None,
) -> SchemaContract:
    source_frame = frame if frame is not None else load_csv(baseline_path)
    profiles = analyze_dataframe(source_frame)
    config = drift_config or DriftConfig()
    columns = {
        name: _build_column_contract(profiles[name], config)
        for name in sorted(profiles)
    }

    return SchemaContract(
        version=CONTRACT_VERSION,
        generated_from={
            "path": baseline_path.as_posix(),
            "file_name": baseline_path.name,
            "rows": int(len(source_frame)),
            "columns": int(len(source_frame.columns)),
            "generated_by": __version__,
        },
        fail_on=fail_on,
        strict_columns=False,
        row_count=_default_row_contract(len(source_frame)),
        columns=columns,
    )


def contract_to_dict(contract: SchemaContract) -> dict[str, Any]:
    payload_columns: dict[str, Any] = {}
    for name, column in sorted(contract.columns.items()):
        payload_columns[name] = {
            "required": column.required,
            "ignore": column.ignore,
            "semantic_type": column.semantic_type,
            "nullable": column.nullable,
            "null_rate_max": column.null_rate_max,
            "unique_ratio_min": column.unique_ratio_min,
            "unique_ratio_max": column.unique_ratio_max,
            "numeric_drift": (
                {"warn": column.numeric_drift.warn, "fail": column.numeric_drift.fail}
                if column.numeric_drift is not None
                else None
            ),
            "category_drift": (
                {
                    "max_new_ratio": column.category_drift.max_new_ratio,
                    "max_removed_ratio": column.category_drift.max_removed_ratio,
                }
                if column.category_drift is not None
                else None
            ),
            "baseline_profile": _profile_to_dict(column.baseline_profile),
        }

    return {
        "version": contract.version,
        "generated_from": contract.generated_from,
        "fail_on": contract.fail_on.value,
        "dataset": {
            "strict_columns": contract.strict_columns,
            "row_count": {
                "baseline": contract.row_count.baseline,
                "min": contract.row_count.minimum,
                "max": contract.row_count.maximum,
            },
        },
        "columns": payload_columns,
    }


def write_contract(contract: SchemaContract, path: Path) -> Path:
    payload = contract_to_dict(contract)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_contract(path: Path) -> SchemaContract:
    if not path.exists():
        raise ContractError(f"Contract file does not exist: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractError(f"Could not read contract file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"Contract file is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise ContractError(f"Contract file must contain a JSON object: {path}")

    dataset = payload.get("dataset", {})
    if not isinstance(dataset, dict):
        raise ContractError("Contract `dataset` section must be a JSON object.")

    row_count = dataset.get("row_count", {})
    if not isinstance(row_count, dict):
        raise ContractError("Contract `dataset.row_count` section must be a JSON object.")

    columns_raw = payload.get("columns", {})
    if not isinstance(columns_raw, dict) or not columns_raw:
        raise ContractError("Contract must contain at least one column definition.")

    columns: dict[str, ColumnContract] = {}
    for name, raw in sorted(columns_raw.items()):
        if not isinstance(raw, dict):
            raise ContractError(f"Contract entry for column `{name}` must be a JSON object.")

        numeric_raw = raw.get("numeric_drift")
        numeric_drift = None
        if isinstance(numeric_raw, dict):
            numeric_drift = NumericDriftPolicy(
                warn=float(numeric_raw.get("warn", DriftConfig().numeric_composite_medium)),
                fail=float(numeric_raw.get("fail", DriftConfig().numeric_composite_high)),
            )

        category_raw = raw.get("category_drift")
        category_drift = None
        if isinstance(category_raw, dict):
            category_drift = CategoryDriftPolicy(
                max_new_ratio=float(category_raw.get("max_new_ratio", 0.2)),
                max_removed_ratio=float(category_raw.get("max_removed_ratio", 0.2)),
            )

        baseline_profile_raw = raw.get("baseline_profile")
        if not isinstance(baseline_profile_raw, dict):
            raise ContractError(f"Column `{name}` is missing a valid `baseline_profile` object.")

        columns[name] = ColumnContract(
            required=bool(raw.get("required", True)),
            ignore=bool(raw.get("ignore", False)),
            semantic_type=str(raw.get("semantic_type", "text")),
            nullable=bool(raw.get("nullable", False)),
            null_rate_max=float(raw.get("null_rate_max", 0.0)),
            unique_ratio_min=_optional_float(raw.get("unique_ratio_min")),
            unique_ratio_max=_optional_float(raw.get("unique_ratio_max")),
            numeric_drift=numeric_drift,
            category_drift=category_drift,
            baseline_profile=_profile_from_dict(baseline_profile_raw),
        )

    version = str(payload.get("version", CONTRACT_VERSION))
    try:
        fail_on = Severity(str(payload.get("fail_on", Severity.HIGH.value)).lower())
    except ValueError as exc:
        raise ContractError(f"Invalid fail_on severity in contract: {payload.get('fail_on')!r}") from exc

    return SchemaContract(
        version=version,
        generated_from=payload.get("generated_from", {}),
        fail_on=fail_on,
        strict_columns=bool(dataset.get("strict_columns", False)),
        row_count=RowCountContract(
            baseline=int(row_count.get("baseline", 0)),
            minimum=int(row_count.get("min", 0)),
            maximum=int(row_count.get("max", 0)),
        ),
        columns=columns,
        path=path,
    )
