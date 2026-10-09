"""Grounded FAQ retrieval with lexical and persistent semantic vector search.

Appointment availability is intentionally excluded from this module. It is mutable
operational state and must be queried through the structured appointment tools.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol, Sequence

import numpy as np

try:
    from dotenv import load_dotenv
except ImportError:  # Keep the module importable in minimal environments.
    def load_dotenv():
        return False

load_dotenv()
logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "can", "do", "does", "for", "from", "have",
    "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "our", "the", "to", "what",
    "when", "where", "which", "who", "with", "you", "your",
}
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_INDEX_DIR = "data/faq_index"
DEFAULT_TOP_K = 3
DEFAULT_MIN_SCORE = 0.45


class EmbeddingModel(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class FAQMatch:
    answer: str
    question: str
    score: float
    source_id: str | None = None
    source: dict[str, str] | None = None


@dataclass
class SemanticFAQIndex:
    """Persistent in-memory representation of a normalized FAQ vector index."""

    entries: list[dict[str, Any]]
    embeddings: np.ndarray
    model_name: str
    content_hash: str
    source_path: str | None = None
    _embedding_model: EmbeddingModel | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_entries(
        cls,
        entries: list[dict[str, Any]],
        *,
        embedding_model: EmbeddingModel | None = None,
        model_name: str | None = None,
        source_path: str | None = None,
    ) -> "SemanticFAQIndex":
        model_name = model_name or os.getenv("FAQ_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        content_hash = faq_fingerprint(entries)
        if not entries:
            return cls(
                entries=[],
                embeddings=np.empty((0, 0), dtype=np.float32),
                model_name=model_name,
                content_hash=content_hash,
                source_path=source_path,
                _embedding_model=embedding_model,
            )
        model = embedding_model or get_default_embedding_model()
        texts = [_entry_search_text(entry) for entry in entries]
        vectors = np.asarray(model.embed_documents(texts), dtype=np.float32)
        vectors = _normalize_rows(vectors)
        if vectors.ndim != 2 or vectors.shape[0] != len(entries):
            raise ValueError("Embedding provider returned an invalid document vector matrix")
        return cls(
            entries=entries,
            embeddings=vectors,
            model_name=model_name,
            content_hash=content_hash,
            source_path=source_path,
            _embedding_model=model,
        )

    def search(
        self,
        query: str,
        *,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE,
        source_ids: set[str] | None = None,
        embedding_model: EmbeddingModel | None = None,
    ) -> list[FAQMatch]:
        if top_k <= 0 or not self.entries or not query.strip():
            return []
        model = embedding_model or self._embedding_model or get_default_embedding_model()
        query_vector = np.asarray(model.embed_query(query), dtype=np.float32).reshape(1, -1)
        query_vector = _normalize_rows(query_vector)
        if query_vector.shape[1] != self.embeddings.shape[1]:
            raise ValueError("Query embedding dimension does not match the FAQ index")

        scores = self.embeddings @ query_vector[0]
        candidate_indices = list(range(len(self.entries)))
        if source_ids is not None:
            candidate_indices = [
                idx
                for idx in candidate_indices
                if self.entries[idx].get("id") is not None
                and str(self.entries[idx]["id"]) in source_ids
            ]
        ranked = sorted(candidate_indices, key=lambda idx: float(scores[idx]), reverse=True)
        matches: list[FAQMatch] = []
        for idx in ranked[:top_k]:
            score = float(scores[idx])
            if score < min_score:
                continue
            entry = self.entries[idx]
            matches.append(
                FAQMatch(
                    answer=entry["answer"],
                    question=entry["question"],
                    score=score,
                    source_id=str(entry["id"]) if entry.get("id") is not None else None,
                    source=entry.get("source"),
                )
            )
        return matches

    def save(self, index_dir: str | Path) -> Path:
        target = Path(index_dir)
        target.mkdir(parents=True, exist_ok=True)
        np.save(target / "embeddings.npy", self.embeddings)
        metadata = {
            "version": 1,
            "model_name": self.model_name,
            "content_hash": self.content_hash,
            "source_path": self.source_path,
            "entries": self.entries,
            "dimension": int(self.embeddings.shape[1]) if self.embeddings.ndim == 2 else 0,
        }
        (target / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return target

    @classmethod
    def load(
        cls,
        index_dir: str | Path,
        *,
        embedding_model: EmbeddingModel | None = None,
    ) -> "SemanticFAQIndex":
        target = Path(index_dir)
        metadata_path = target / "metadata.json"
        embeddings_path = target / "embeddings.npy"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        embeddings = np.load(embeddings_path, allow_pickle=False)
        entries = metadata.get("entries", [])
        if not isinstance(entries, list) or embeddings.ndim != 2 or embeddings.shape[0] != len(entries):
            raise ValueError("Persisted FAQ index is malformed")
        expected_dimension = int(metadata.get("dimension", embeddings.shape[1]))
        if embeddings.shape[1] != expected_dimension:
            raise ValueError("Persisted FAQ index dimension is inconsistent")
        return cls(
            entries=entries,
            embeddings=_normalize_rows(embeddings),
            model_name=str(metadata["model_name"]),
            content_hash=str(metadata["content_hash"]),
            source_path=metadata.get("source_path"),
            _embedding_model=embedding_model,
        )


def tokenize(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(text.casefold()) if token not in _STOPWORDS}


def _clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _validated_entry(item: Any) -> dict[str, Any] | None:
    """Return a normalized FAQ record only when required fields are usable."""
    if not isinstance(item, dict):
        return None
    question = _clean_string(item.get("question"))
    answer = _clean_string(item.get("answer"))
    if question is None or answer is None:
        return None

    normalized: dict[str, Any] = {"question": question, "answer": answer}
    if item.get("id") is not None:
        source_id = _clean_string(str(item["id"]))
        if source_id is not None:
            normalized["id"] = source_id

    keywords = item.get("keywords", [])
    if isinstance(keywords, str):
        cleaned_keywords = [_clean_string(keywords)]
    elif isinstance(keywords, list):
        cleaned_keywords = [_clean_string(value) for value in keywords]
    else:
        cleaned_keywords = []
    normalized["keywords"] = [value for value in cleaned_keywords if value]

    source = item.get("source")
    if isinstance(source, dict):
        cleaned_source = {
            key: cleaned
            for key in ("title", "document", "url", "reviewed_at", "owner")
            if (cleaned := _clean_string(source.get(key))) is not None
        }
        if cleaned_source:
            normalized["source"] = cleaned_source
    return normalized


def load_faq(path: str | Path) -> list[dict[str, Any]]:
    """Load only valid FAQ records; malformed sources fail closed."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        logger.exception("FAQ knowledge source could not be loaded")
        return []
    if not isinstance(payload, list):
        logger.error("FAQ knowledge source must be a JSON list")
        return []
    return [entry for item in payload if (entry := _validated_entry(item)) is not None]


def faq_fingerprint(entries: Sequence[dict[str, Any]]) -> str:
    canonical = json.dumps(
        list(entries),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _entry_search_text(entry: dict[str, Any]) -> str:
    parts = [entry["question"]]
    parts.extend(str(keyword) for keyword in entry.get("keywords", []) if isinstance(keyword, str))
    return " ".join(parts)


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim != 2:
        raise ValueError("Embedding matrix must be two-dimensional")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("Embedding provider returned a zero vector")
    return matrix / norms


@lru_cache(maxsize=1)
def get_default_embedding_model() -> EmbeddingModel:
    """Return the configured OpenAI embedding model lazily."""
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=os.getenv("FAQ_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
    )


def build_semantic_index(
    entries: list[dict[str, Any]],
    *,
    embedding_model: EmbeddingModel | None = None,
    model_name: str | None = None,
    source_path: str | None = None,
) -> SemanticFAQIndex:
    return SemanticFAQIndex.from_entries(
        entries,
        embedding_model=embedding_model,
        model_name=model_name,
        source_path=source_path,
    )


def ingest_faq(
    source_path: str | Path,
    index_dir: str | Path = DEFAULT_INDEX_DIR,
    *,
    embedding_model: EmbeddingModel | None = None,
    model_name: str | None = None,
) -> SemanticFAQIndex:
    """Validate, embed, and persist the approved FAQ corpus."""
    source = Path(source_path)
    entries = load_faq(source)
    index = build_semantic_index(
        entries,
        embedding_model=embedding_model,
        model_name=model_name,
        source_path=str(source),
    )
    index.save(index_dir)
    return index


def load_or_build_faq_index(
    source_path: str | Path,
    index_dir: str | Path = DEFAULT_INDEX_DIR,
    *,
    embedding_model: EmbeddingModel | None = None,
    model_name: str | None = None,
) -> SemanticFAQIndex:
    source = Path(source_path)
    entries = load_faq(source)
    resolved_model_name = model_name or os.getenv("FAQ_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    if not entries:
        return SemanticFAQIndex.from_entries(
            [],
            embedding_model=embedding_model,
            model_name=resolved_model_name,
            source_path=str(source),
        )

    expected_hash = faq_fingerprint(entries)
    try:
        cached = SemanticFAQIndex.load(index_dir, embedding_model=embedding_model)
        if cached.content_hash == expected_hash and cached.model_name == resolved_model_name:
            return cached
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        logger.info("No valid reusable FAQ vector index found; rebuilding it")

    return ingest_faq(
        source,
        index_dir,
        embedding_model=embedding_model,
        model_name=resolved_model_name,
    )


def retrieve_semantic_faq(
    query: str,
    *,
    entries: list[dict[str, Any]] | None = None,
    index: SemanticFAQIndex | None = None,
    source_path: str | Path | None = None,
    index_dir: str | Path = DEFAULT_INDEX_DIR,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_MIN_SCORE,
    source_ids: set[str] | None = None,
    embedding_model: EmbeddingModel | None = None,
) -> FAQMatch | None:
    """Retrieve one grounded FAQ answer; return None below the evidence threshold."""
    if not query.strip():
        return None
    if index is None:
        if entries is not None:
            index = build_semantic_index(entries, embedding_model=embedding_model)
        elif source_path is not None:
            index = load_or_build_faq_index(
                source_path,
                index_dir,
                embedding_model=embedding_model,
            )
        else:
            raise ValueError("entries, index, or source_path is required")

    matches = index.search(
        query,
        top_k=top_k,
        min_score=min_score,
        source_ids=source_ids,
        embedding_model=embedding_model,
    )
    return matches[0] if matches else None


def evaluate_retrieval(
    evaluation_cases: Sequence[dict[str, Any]],
    index: SemanticFAQIndex,
    *,
    embedding_model: EmbeddingModel | None = None,
    k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_MIN_SCORE,
) -> dict[str, float | int]:
    """Evaluate top-k retrieval with hit-rate, MRR, and safe no-answer rate."""
    supported = [case for case in evaluation_cases if case.get("expected_source_id") is not None]
    unsupported = [case for case in evaluation_cases if case.get("expected_source_id") is None]
    hits = 0
    reciprocal_rank_total = 0.0
    no_answer = 0

    for case in supported:
        expected = str(case["expected_source_id"])
        results = index.search(
            str(case["query"]),
            top_k=k,
            min_score=min_score,
            embedding_model=embedding_model,
        )
        ids = [match.source_id for match in results]
        if expected in ids:
            hits += 1
            reciprocal_rank_total += 1.0 / (ids.index(expected) + 1)

    for case in unsupported:
        results = index.search(
            str(case["query"]),
            top_k=k,
            min_score=min_score,
            embedding_model=embedding_model,
        )
        if not results:
            no_answer += 1

    return {
        "total_cases": len(evaluation_cases),
        "supported_cases": len(supported),
        "unsupported_cases": len(unsupported),
        "hit_rate_at_k": hits / len(supported) if supported else 0.0,
        "mrr": reciprocal_rank_total / len(supported) if supported else 0.0,
        "no_answer_rate": no_answer / len(unsupported) if unsupported else 0.0,
    }


# Backwards-compatible deterministic lexical baseline.
def retrieve_faq(
    query: str,
    entries: list[dict[str, Any]],
    *,
    min_score: float = 0.20,
) -> FAQMatch | None:
    """Rank FAQ entries by query-term coverage as a deterministic baseline."""
    query_terms = tokenize(query)
    if not query_terms:
        return None
    best: FAQMatch | None = None
    for entry in entries:
        searchable = [entry.get("question", "")]
        searchable.extend(value for value in entry.get("keywords", []) if isinstance(value, str))
        terms = set().union(*(tokenize(value) for value in searchable))
        if not terms:
            continue
        overlap = len(query_terms & terms)
        score = overlap / len(query_terms)
        candidate = FAQMatch(
            answer=entry["answer"].strip(),
            question=entry["question"].strip(),
            score=score,
            source_id=str(entry["id"]) if entry.get("id") is not None else None,
            source=entry.get("source"),
        )
        if best is None or candidate.score > best.score:
            best = candidate
    return best if best is not None and best.score >= min_score else None


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Build a persistent semantic FAQ index.")
    parser.add_argument("--source", default="data/clinic_faq.json")
    parser.add_argument("--index-dir", default=DEFAULT_INDEX_DIR)
    parser.add_argument("--model", default=os.getenv("FAQ_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL))
    args = parser.parse_args()
    index = ingest_faq(args.source, args.index_dir, model_name=args.model)
    print(json.dumps({
        "source": str(args.source),
        "index_dir": str(args.index_dir),
        "documents": len(index.entries),
        "dimension": int(index.embeddings.shape[1]) if index.embeddings.ndim == 2 else 0,
        "model": index.model_name,
        "content_hash": index.content_hash,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
