"""Explainable, conservative subject routing."""

from __future__ import annotations

import json
import re
from importlib import resources
from typing import Dict, List


def load_keyword_profiles() -> Dict[str, Dict[str, int]]:
    profiles: Dict[str, Dict[str, int]] = {}
    root = resources.files("assignment_assistant.overlay_data")
    for item in root.iterdir():
        if not item.name.endswith(".json"):
            continue
        payload = json.loads(item.read_text(encoding="utf-8"))
        discipline = str(payload["id"])
        keywords = payload.get("routing_keywords", {})
        if keywords:
            profiles[discipline] = {
                str(term): int(weight) for term, weight in keywords.items()
            }
    return profiles


def _count_term(text: str, term: str) -> int:
    pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def route_subject(text: str, configured: str = "auto") -> Dict[str, object]:
    configured = configured.lower()
    if configured != "auto":
        return {
            "discipline": configured,
            "confidence": 1.0,
            "requires_confirmation": False,
            "reason": "Explicit configuration override",
            "scores": {configured: 1},
            "matched_terms": {},
        }

    profiles = load_keyword_profiles()
    scores: Dict[str, int] = {}
    matches: Dict[str, List[str]] = {}
    for discipline, weighted_terms in profiles.items():
        total = 0
        found: List[str] = []
        for term, weight in weighted_terms.items():
            occurrences = min(_count_term(text, term), 5)
            if occurrences:
                total += occurrences * weight
                found.append(term)
        scores[discipline] = total
        matches[discipline] = found

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_name, best_score = ranked[0]
    second_score = ranked[1][1]
    if best_score == 0:
        return {
            "discipline": "generic",
            "confidence": 0.0,
            "requires_confirmation": True,
            "reason": "No discipline-specific evidence was found",
            "scores": scores,
            "matched_terms": matches,
        }

    confidence = round((best_score - second_score) / max(best_score, 1), 3)
    mixed = second_score > 0 and second_score / best_score >= 0.75
    low_signal = best_score < 5
    return {
        "discipline": best_name,
        "confidence": confidence,
        "requires_confirmation": bool(mixed or low_signal),
        "reason": (
            "Mixed or weak evidence; user confirmation required"
            if mixed or low_signal
            else "Highest weighted discipline score"
        ),
        "scores": scores,
        "matched_terms": matches,
    }
