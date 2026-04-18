from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

from jinja2 import Environment

from .config import normalize_report_formats
from .models import ColumnMatch, ComparisonResult, Finding, Severity
from .risk import calculate_stability_score, overall_severity, severity_label, summarize_findings
from .utils import (
    format_change,
    format_number,
    format_percent,
    highest_severity,
    sort_findings,
)

SEVERITY_ORDER = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]
REPORT_SCHEMA_VERSION = "0.3"


def _load_template(name: str) -> str:
    from importlib.resources import files

    return files("schema_sentinel").joinpath(f"templates/{name}").read_text(encoding="utf-8")


def _finding_to_dict(finding: Finding) -> dict[str, object]:
    return {
        "code": finding.code,
        "severity": finding.severity.value,
        "severity_label": finding.severity.title,
        "title": finding.title,
        "message": finding.message,
        "affected_columns": ", ".join(finding.affected_columns) if finding.affected_columns else "-",
        "old_value": finding.old_value or "-",
        "new_value": finding.new_value or "-",
        "recommendation": finding.recommendation or "-",
        "details": finding.details,
    }


def _rename_to_dict(match: ColumnMatch) -> dict[str, object]:
    return {
        "old_column": match.old_column,
        "new_column": match.new_column,
        "confidence": match.confidence,
        "confidence_label": format_percent(match.confidence),
        "name_similarity": match.name_similarity,
        "name_similarity_label": format_percent(match.name_similarity),
        "profile_similarity": match.profile_similarity,
        "profile_similarity_label": format_percent(match.profile_similarity),
        "reason": match.reason,
        "details": match.details,
    }


def _column_row(
    result: ComparisonResult,
    column: str,
    column_findings: list[Finding],
) -> dict[str, object]:
    old_profile = result.old_profiles[column]
    new_profile = result.new_profiles[column]
    severity = highest_severity(column_findings)
    notes = "; ".join([finding.title for finding in sort_findings(column_findings)[:3]] or ["-"])
    if old_profile.semantic_type == "numeric" and new_profile.semantic_type == "numeric":
        drift_note = "Numeric distribution changed"
    elif old_profile.semantic_type != new_profile.semantic_type:
        drift_note = f"{old_profile.semantic_type} -> {new_profile.semantic_type}"
    else:
        drift_note = "Stable shape"

    return {
        "column": column,
        "severity": severity.value,
        "severity_label": severity.title if column_findings else "Low",
        "old_type": old_profile.semantic_type,
        "new_type": new_profile.semantic_type,
        "old_null": format_percent(old_profile.null_rate),
        "new_null": format_percent(new_profile.null_rate),
        "old_unique": format_percent(old_profile.unique_ratio),
        "new_unique": format_percent(new_profile.unique_ratio),
        "old_examples": ", ".join(old_profile.sample_values[:3]) or "-",
        "new_examples": ", ".join(new_profile.sample_values[:3]) or "-",
        "notes": notes,
        "drift_summary": drift_note,
    }


def _result_labels(result: ComparisonResult) -> dict[str, object]:
    if result.mode == "validate":
        contract_name = result.contract_path.name if result.contract_path else "schema-contract.json"
        return {
            "hero_title": "Validate data against a committed contract.",
            "hero_copy": (
                f"Validating <strong>{result.new_path.name}</strong> against <strong>{contract_name}</strong>. "
                "The report surfaces contract breaches first, then shows how the observed data "
                "compares with the baseline profile stored in the contract."
            ),
            "summary_intro": "Contract breaches are grouped into dense cards so CI reviewers can scan the result fast.",
            "findings_title": "Contract breaches",
            "findings_intro": "Blocking contract violations appear first so release decisions stay obvious.",
            "columns_title": "Column-level validation",
            "columns_intro": (
                "This table compares the observed dataset with the baseline profile captured in the contract."
            ),
            "health_intro": "A compact view of the contract baseline versus the current dataset shape.",
            "added_label": "Unexpected columns",
            "added_note": "Present outside the contract",
            "removed_label": "Missing required",
            "removed_note": "Required but absent",
            "finding_label_plural": "breaches",
            "mode_label": "Validate",
            "show_rename_section": False,
        }

    return {
        "hero_title": "Catch drift before the pipeline breaks.",
        "hero_copy": (
            f"Comparing <strong>{result.old_path.name}</strong> to <strong>{result.new_path.name}</strong>. "
            "The report highlights structural changes first, then drills into null-rate shifts, "
            "rename suggestions, category drift, and numeric movement that could affect downstream consumers."
        ),
        "summary_intro": "Small, dense cards make it easy to scan the result in seconds and still preserve detail.",
        "findings_title": "Findings by severity",
        "findings_intro": (
            "Critical and high findings appear first so the most dangerous regressions are impossible to miss."
        ),
        "columns_title": "Column-level diff",
        "columns_intro": (
            "This table captures the shared columns and shows how the shape, null rate, "
            "and uniqueness changed from old to new."
        ),
        "health_intro": "A compact status view that pairs the core counts with a quick look at the dataset shape.",
        "added_label": "Added columns",
        "added_note": "New schema fields",
        "removed_label": "Removed columns",
        "removed_note": "Missing schema fields",
        "finding_label_plural": "findings",
        "mode_label": "Compare",
        "show_rename_section": True,
    }


def build_context(result: ComparisonResult) -> dict[str, object]:
    labels = _result_labels(result)
    findings = sort_findings(result.findings)
    severity_groups: dict[str, list[dict[str, object]]] = {severity.title: [] for severity in SEVERITY_ORDER}
    column_findings: dict[str, list[Finding]] = defaultdict(list)

    for finding in findings:
        severity_groups[finding.severity.title].append(_finding_to_dict(finding))
        for column in finding.affected_columns:
            column_findings[column].append(finding)

    column_rows = [_column_row(result, column, column_findings[column]) for column in result.shared_columns]
    rename_suggestions = [_rename_to_dict(match) for match in result.rename_suggestions]

    summary = summarize_findings(result.findings)
    overall = severity_label(overall_severity(result.findings), result.findings)
    score = calculate_stability_score(result.findings)
    breaches = [_finding_to_dict(finding) for finding in sort_findings(result.contract_breaches)]

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "mode": result.mode,
        "mode_label": labels["mode_label"],
        "project_name": "Schema Sentinel",
        "generated_at": result.generated_at.strftime("%Y-%m-%d %H:%M UTC"),
        "old_path": result.old_path.name,
        "new_path": result.new_path.name,
        "contract_path": str(result.contract_path) if result.contract_path else None,
        "contract_name": result.contract_path.name if result.contract_path else None,
        "contract_metadata": result.contract_metadata,
        "old_rows": format_number(result.old_rows),
        "new_rows": format_number(result.new_rows),
        "old_columns": format_number(result.old_columns),
        "new_columns": format_number(result.new_columns),
        "added_columns": result.added_columns,
        "removed_columns": result.removed_columns,
        "shared_columns": result.shared_columns,
        "rename_suggestions": rename_suggestions,
        "rename_count": len(rename_suggestions),
        "row_change": format_change(result.old_rows, result.new_rows),
        "column_change": format_change(result.old_columns, result.new_columns),
        "overall_risk": overall,
        "overall_risk_lower": overall.lower(),
        "stability_score": score,
        "summary": summary,
        "findings": [_finding_to_dict(finding) for finding in findings],
        "breaches": breaches,
        "findings_by_severity": severity_groups,
        "column_rows": column_rows,
        "recommendations": result.recommendations,
        "output_dir": str(result.output_dir) if result.output_dir else "outputs",
        "output_files": {name: path.name for name, path in result.output_files.items()},
        "top_findings": [_finding_to_dict(finding) for finding in findings[:5]],
        "counts": {
            "added": len(result.added_columns),
            "removed": len(result.removed_columns),
            "shared": len(result.shared_columns),
            "renamed": len(result.rename_suggestions),
        },
        "has_critical": summary["critical"] > 0,
        "has_renames": bool(result.rename_suggestions),
        "hero_title": labels["hero_title"],
        "hero_copy": labels["hero_copy"],
        "summary_intro": labels["summary_intro"],
        "findings_title": labels["findings_title"],
        "findings_intro": labels["findings_intro"],
        "columns_title": labels["columns_title"],
        "columns_intro": labels["columns_intro"],
        "health_intro": labels["health_intro"],
        "added_label": labels["added_label"],
        "added_note": labels["added_note"],
        "removed_label": labels["removed_label"],
        "removed_note": labels["removed_note"],
        "finding_label_plural": labels["finding_label_plural"],
        "show_rename_section": labels["show_rename_section"],
    }


def render_markdown_report(result: ComparisonResult) -> str:
    template_text = _load_template("summary.md.j2")
    env = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(template_text)
    return template.render(**build_context(result))


def render_html_report(result: ComparisonResult) -> str:
    template_text = _load_template("report.html.j2")
    env = Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(template_text)
    return template.render(**build_context(result))


def render_json_report(result: ComparisonResult) -> str:
    payload = build_context(result)
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)


def render_github_step_summary(result: ComparisonResult) -> str:
    context = build_context(result)
    lines = [
        "## Schema Sentinel",
        "",
        f"- Mode: `{context['mode']}`",
        f"- Overall risk: **{context['overall_risk']}**",
        f"- Stability score: **{context['stability_score']}/100**",
        f"- {context['finding_label_plural'].title()}: **{context['summary']['total']}**",
    ]

    if context["mode"] == "validate" and context["contract_name"]:
        lines.append(f"- Contract: `{context['contract_name']}`")
        generated_from = context["contract_metadata"].get("generated_from", {})
        if isinstance(generated_from, dict) and generated_from.get("file_name"):
            lines.append(f"- Baseline source: `{generated_from['file_name']}`")
    else:
        lines.append(f"- Compared files: `{context['old_path']}` -> `{context['new_path']}`")

    if context["top_findings"]:
        lines.extend(["", "### Top issues"])
        for finding in context["top_findings"]:
            lines.append(f"- **{finding['severity_label']}** {finding['title']}")

    if context["output_files"]:
        lines.extend(["", "### Artifacts"])
        for name, path in context["output_files"].items():
            lines.append(f"- `{name}`: `{path}`")

    return "\n".join(lines) + "\n"


def write_github_step_summary(result: ComparisonResult) -> None:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    Path(summary_path).write_text(render_github_step_summary(result), encoding="utf-8")


def write_reports(result: ComparisonResult, output_dir: Path, formats: tuple[str, ...]) -> dict[str, Path]:
    from .utils import make_output_dir

    make_output_dir(output_dir)
    written: dict[str, Path] = {}
    canonical_formats = normalize_report_formats(formats)

    planned_files: dict[str, Path] = {}
    if "markdown" in canonical_formats:
        planned_files["markdown"] = output_dir / "summary.md"
    if "html" in canonical_formats:
        planned_files["html"] = output_dir / "report.html"
    if "json" in canonical_formats:
        planned_files["json"] = output_dir / "report.json"

    result.output_files = planned_files

    if "markdown" in planned_files:
        planned_files["markdown"].write_text(render_markdown_report(result), encoding="utf-8")
        written["markdown"] = planned_files["markdown"]

    if "html" in planned_files:
        planned_files["html"].write_text(render_html_report(result), encoding="utf-8")
        written["html"] = planned_files["html"]

    if "json" in planned_files:
        planned_files["json"].write_text(render_json_report(result), encoding="utf-8")
        written["json"] = planned_files["json"]

    return written
