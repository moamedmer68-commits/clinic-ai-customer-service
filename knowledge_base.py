"""Deterministic, evidence-bounded retrieval for approved clinic FAQ content.

Appointment availability is intentionally excluded: it is structured live state
and must be queried through toolkit.tools against the authoritative schedule.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


@dataclass(frozen=True)
class FAQMatch:
    answer: str
    question: str
    score: float
    source_id: str | None = None


def tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.casefold()))


def load_faq(path: str | Path) -> list[dict[str, Any]]:
    """Load only valid FAQ records; malformed files fail closed to no evidence."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("FAQ knowledge source could not be loaded")
        return []
    if not isinstance(payload, list):
        logger.error("FAQ knowledge source must be a JSON list")
        return []
    valid = []
    for item in payload:
        if (isinstance(item, dict) and isinstance(item.get("question"), str)
                and isinstance(item.get("answer"), str) and item["question"].strip()
                and item["answer"].strip()):
            valid.append(item)
    return valid


def retrieve_faq(query: str, entries: list[dict[str, Any]], *, min_score: float = 0.20) -> FAQMatch | None:
    """Rank approved FAQ entries by query-term coverage; return None below threshold."""
    query_terms = tokenize(query)
    if not query_terms:
        return None
    best: FAQMatch | None = None
    for entry in entries:
        searchable = [entry.get("question", "")]
        keywords = entry.get("keywords", [])
        if isinstance(keywords, str):
            searchable.append(keywords)
        elif isinstance(keywords, list):
            searchable.extend(value for value in keywords if isinstance(value, str))
        terms = set().union(*(tokenize(value) for value in searchable))
        if not terms:
            continue
        overlap = len(query_terms & terms)
        score = overlap / len(query_terms)
        candidate = FAQMatch(entry["answer"].strip(), entry["question"].strip(), score,
                             str(entry["id"]) if entry.get("id") is not None else None)
        if best is None or candidate.score > best.score:
            best = candidate
    return best if best is not None and best.score >= min_score else None
