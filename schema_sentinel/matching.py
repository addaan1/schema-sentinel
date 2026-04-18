from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher
from itertools import product

from .config import MatchingConfig
from .models import ColumnMatch, ColumnProfile
from .utils import clamp, normalize_text, unique_preserving_order

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _normalize_column_name(name: str) -> str:
    tokenized = _CAMEL_SPLIT_RE.sub(" ", name)
    tokenized = tokenized.replace("-", " ").replace("_", " ")
    cleaned = _TOKEN_SPLIT_RE.sub(" ", tokenized.lower())
    return " ".join(cleaned.split())


def _token_set(name: str) -> set[str]:
    return {token for token in _normalize_column_name(name).split() if token}


def _sequence_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def _sample_signature(profile: ColumnProfile) -> set[str]:
    return {
        normalize_text(value)
        for value in unique_preserving_order(
            list(profile.sample_values) + list(profile.distinct_values) + [value for value, _ in profile.top_values],
            limit=12,
        )
        if normalize_text(value)
    }


def _jaccard_similarity(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _type_compatibility(old: ColumnProfile, new: ColumnProfile) -> float:
    if old.semantic_type == new.semantic_type:
        return 1.0

    textish = {"categorical", "text", "boolean"}
    if old.semantic_type in textish and new.semantic_type in textish:
        return 0.82
    if "empty" in {old.semantic_type, new.semantic_type}:
        return 0.25
    if {old.semantic_type, new.semantic_type} <= {"numeric", "text"}:
        return 0.55
    return 0.4


def _numeric_similarity(old: ColumnProfile, new: ColumnProfile) -> float:
    if old.numeric_summary is None or new.numeric_summary is None:
        return 0.0

    metrics = {
        "mean": (old.numeric_summary.mean, new.numeric_summary.mean),
        "median": (old.numeric_summary.median, new.numeric_summary.median),
        "std": (old.numeric_summary.std, new.numeric_summary.std),
        "minimum": (old.numeric_summary.minimum, new.numeric_summary.minimum),
        "maximum": (old.numeric_summary.maximum, new.numeric_summary.maximum),
        "p95": (old.numeric_summary.p95, new.numeric_summary.p95),
    }

    similarities: list[float] = []
    for left, right in metrics.values():
        if left is None or right is None:
            continue
        denominator = max(abs(left), abs(right), 1.0)
        similarities.append(1.0 - clamp(abs(left - right) / denominator, 0.0, 1.0))

    if not similarities:
        return 0.0
    return sum(similarities) / len(similarities)


def _profile_similarity(old: ColumnProfile, new: ColumnProfile) -> tuple[float, dict[str, float]]:
    old_signature = _sample_signature(old)
    new_signature = _sample_signature(new)

    null_similarity = 1.0 - clamp(abs(new.null_rate - old.null_rate) / 0.5, 0.0, 1.0)
    unique_similarity = 1.0 - clamp(abs(new.unique_ratio - old.unique_ratio) / 0.75, 0.0, 1.0)
    sample_similarity = _jaccard_similarity(old_signature, new_signature)
    type_similarity = _type_compatibility(old, new)
    numeric_similarity = _numeric_similarity(old, new)
    category_similarity = _jaccard_similarity(
        old_signature | set(old.distinct_values),
        new_signature | set(new.distinct_values),
    )

    if old.semantic_type == "numeric" and new.semantic_type == "numeric":
        value_similarity = max(numeric_similarity, sample_similarity)
    else:
        value_similarity = max(sample_similarity, category_similarity)

    profile_similarity = (
        null_similarity * 0.2
        + unique_similarity * 0.2
        + value_similarity * 0.35
        + type_similarity * 0.25
    )
    profile_similarity = clamp(profile_similarity, 0.0, 1.0)

    return profile_similarity, {
        "null_similarity": null_similarity,
        "unique_similarity": unique_similarity,
        "sample_similarity": sample_similarity,
        "type_similarity": type_similarity,
        "numeric_similarity": numeric_similarity,
        "category_similarity": category_similarity,
        "value_similarity": value_similarity,
    }


def score_column_match(
    old: ColumnProfile,
    new: ColumnProfile,
    matching: MatchingConfig | None = None,
) -> tuple[float, dict[str, float]]:
    config = matching or MatchingConfig()
    normalized_old = _normalize_column_name(old.name)
    normalized_new = _normalize_column_name(new.name)
    name_similarity = max(
        _sequence_similarity(normalized_old, normalized_new),
        _jaccard_similarity(_token_set(old.name), _token_set(new.name)),
    )
    profile_similarity, parts = _profile_similarity(old, new)
    type_similarity = parts["type_similarity"]

    confidence = (
        name_similarity * config.name_weight
        + profile_similarity * config.data_weight
        + type_similarity * config.type_weight
    )
    confidence = clamp(confidence, 0.0, 1.0)

    return confidence, {
        "name_similarity": name_similarity,
        "profile_similarity": profile_similarity,
        **parts,
    }


def match_renamed_columns(
    old_profiles: dict[str, ColumnProfile],
    new_profiles: dict[str, ColumnProfile],
    removed_columns: Iterable[str],
    added_columns: Iterable[str],
    matching: MatchingConfig | None = None,
) -> list[ColumnMatch]:
    config = matching or MatchingConfig()
    candidates: list[tuple[float, str, str, dict[str, float]]] = []

    for old_name, new_name in product(removed_columns, added_columns):
        old_profile = old_profiles[old_name]
        new_profile = new_profiles[new_name]
        confidence, details = score_column_match(old_profile, new_profile, config)
        if confidence < config.rename_threshold:
            continue
        candidates.append((confidence, old_name, new_name, details))

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))

    matched_old: set[str] = set()
    matched_new: set[str] = set()
    matches: list[ColumnMatch] = []

    for confidence, old_name, new_name, details in candidates:
        if old_name in matched_old or new_name in matched_new:
            continue

        matched_old.add(old_name)
        matched_new.add(new_name)

        reason = (
            f"Name similarity {details['name_similarity']:.2f}, "
            f"profile similarity {details['profile_similarity']:.2f}"
        )
        if details["numeric_similarity"] > 0:
            reason += f", numeric similarity {details['numeric_similarity']:.2f}"
        if details["category_similarity"] > 0:
            reason += f", category similarity {details['category_similarity']:.2f}"

        matches.append(
            ColumnMatch(
                old_column=old_name,
                new_column=new_name,
                confidence=confidence,
                name_similarity=details["name_similarity"],
                profile_similarity=details["profile_similarity"],
                reason=reason,
                details=details,
            )
        )

    return matches
