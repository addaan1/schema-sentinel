from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ConfigurationError
from .models import Severity

DEFAULT_CONFIG_FILENAME = "config.json"
DEFAULT_OUTPUT_DIR = Path("outputs")
DEFAULT_OUTPUT_FORMATS = ("markdown", "html")
DEFAULT_RENAME_THRESHOLD = 0.78


def _normalize_severity(value: Any) -> Severity:
    if isinstance(value, Severity):
        return value
    if value is None:
        return Severity.HIGH
    try:
        return Severity(str(value).strip().lower())
    except ValueError as exc:  # pragma: no cover - defensive parsing
        raise ConfigurationError(f"Invalid severity value in config: {value!r}") from exc


def normalize_report_formats(value: str | Iterable[str] | None) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_OUTPUT_FORMATS

    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return DEFAULT_OUTPUT_FORMATS
        aliases = {
            "both": ("markdown", "html"),
            "all": ("markdown", "html", "json"),
        }
        if normalized in aliases:
            return aliases[normalized]
        if normalized in {"markdown", "html", "json"}:
            return (normalized,)
        raise ConfigurationError(
            "Unknown report format. Expected markdown, html, json, both, or all."
        )

    formats: list[str] = []
    for item in value:
        formats.extend(normalize_report_formats(item))

    deduplicated: list[str] = []
    seen: set[str] = set()
    for item in formats:
        if item not in seen:
            seen.add(item)
            deduplicated.append(item)

    if not deduplicated:
        return DEFAULT_OUTPUT_FORMATS
    return tuple(deduplicated)


@dataclass(frozen=True)
class OutputConfig:
    directory: Path = DEFAULT_OUTPUT_DIR
    formats: tuple[str, ...] = DEFAULT_OUTPUT_FORMATS
    fail_on: Severity = Severity.HIGH


@dataclass(frozen=True)
class MatchingConfig:
    rename_threshold: float = DEFAULT_RENAME_THRESHOLD
    name_weight: float = 0.35
    data_weight: float = 0.55
    type_weight: float = 0.10


@dataclass(frozen=True)
class DriftConfig:
    row_low: float = 0.05
    row_medium: float = 0.2
    row_high: float = 0.5
    null_rate_low: float = 0.05
    null_rate_medium: float = 0.12
    null_rate_high: float = 0.25
    unique_ratio_low: float = 0.12
    unique_ratio_medium: float = 0.25
    numeric_composite_medium: float = 0.15
    numeric_composite_high: float = 0.35


@dataclass(frozen=True)
class AppConfig:
    output: OutputConfig = field(default_factory=OutputConfig)
    matching: MatchingConfig = field(default_factory=MatchingConfig)
    drift: DriftConfig = field(default_factory=DriftConfig)
    source_path: Path | None = None


def _coerce_path(value: Any, base_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base_path / path


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - file system edge case
        raise ConfigurationError(f"Could not read config file: {path}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Config file is not valid JSON: {path}") from exc

    if not isinstance(parsed, dict):
        raise ConfigurationError(f"Config file must contain a JSON object: {path}")

    return parsed


def _parse_output(section: dict[str, Any], base_path: Path) -> OutputConfig:
    directory_value = section.get("directory", DEFAULT_OUTPUT_DIR)
    directory = _coerce_path(directory_value, base_path)
    formats_value = section.get("formats")
    if formats_value is None:
        formats_value = section.get("format")
    formats = normalize_report_formats(formats_value)
    fail_on = _normalize_severity(section.get("fail_on", Severity.HIGH))
    return OutputConfig(directory=directory, formats=formats, fail_on=fail_on)


def _parse_matching(section: dict[str, Any]) -> MatchingConfig:
    return MatchingConfig(
        rename_threshold=float(section.get("rename_threshold", DEFAULT_RENAME_THRESHOLD)),
        name_weight=float(section.get("name_weight", 0.35)),
        data_weight=float(section.get("data_weight", 0.55)),
        type_weight=float(section.get("type_weight", 0.10)),
    )


def _parse_drift(section: dict[str, Any]) -> DriftConfig:
    defaults = DriftConfig()
    return DriftConfig(
        row_low=float(section.get("row_low", defaults.row_low)),
        row_medium=float(section.get("row_medium", defaults.row_medium)),
        row_high=float(section.get("row_high", defaults.row_high)),
        null_rate_low=float(section.get("null_rate_low", defaults.null_rate_low)),
        null_rate_medium=float(section.get("null_rate_medium", defaults.null_rate_medium)),
        null_rate_high=float(section.get("null_rate_high", defaults.null_rate_high)),
        unique_ratio_low=float(section.get("unique_ratio_low", defaults.unique_ratio_low)),
        unique_ratio_medium=float(section.get("unique_ratio_medium", defaults.unique_ratio_medium)),
        numeric_composite_medium=float(section.get("numeric_composite_medium", defaults.numeric_composite_medium)),
        numeric_composite_high=float(section.get("numeric_composite_high", defaults.numeric_composite_high)),
    )


def load_config(path: Path | None = None, *, cwd: Path | None = None) -> AppConfig:
    base_cwd = cwd or Path.cwd()
    if path is not None:
        config_path = path
        if not config_path.exists():
            raise ConfigurationError(f"Config file does not exist: {config_path}")
    else:
        config_path = base_cwd / DEFAULT_CONFIG_FILENAME
        if not config_path.exists():
            return AppConfig()

    if not config_path.exists():  # pragma: no cover - defensive fallback
        return AppConfig()

    data = _load_json(config_path)
    base_path = config_path.parent

    output_section = data.get("output", {})
    matching_section = data.get("matching", {})
    drift_section = data.get("drift", {})

    output = _parse_output(output_section if isinstance(output_section, dict) else {}, base_path)
    matching = _parse_matching(matching_section if isinstance(matching_section, dict) else {})
    drift = _parse_drift(drift_section if isinstance(drift_section, dict) else {})

    return AppConfig(output=output, matching=matching, drift=drift, source_path=config_path)
