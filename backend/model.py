"""RAG-based educational keyword filter.

This module replaces the legacy TF-IDF + Random Forest training script.
The filter treats the knowledge base as the source of truth, embeds those
documents, retrieves the nearest evidence for a candidate keyphrase, and
accepts the phrase when the retrieved evidence is sufficiently similar.

The real project knowledge base can be supplied later without changing code:

- set ``RAG_KB_PATH`` or ``EDUCATIONAL_KB_PATH`` to a JSON, JSONL, CSV, TXT,
  or Markdown file; or
- place a JSONL file at ``backend/app/educational_kb.jsonl``.

Until that file exists, a small built-in educational seed corpus keeps the
recommender usable in local development.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

try:
    from app.vectorizer import embed_text
except ModuleNotFoundError:  # Allows importing as ``backend.model`` in tests.
    from backend.app.vectorizer import embed_text


_BACKEND_DIR = Path(__file__).resolve().parent
_DEFAULT_KB_RELATIVE_PATH = Path("app") / "educational_kb.jsonl"
_DEFAULT_CACHE_RELATIVE_PATH = Path("app") / "rag_embeddings.npz"


DEFAULT_EDUCATIONAL_KB: list[str] = [
    "computer science",
    "programming",
    "software engineering",
    "algorithms",
    "data structures",
    "operating systems",
    "computer networks",
    "distributed systems",
    "version control",
    "git",
    "software testing",
    "debugging",
    "web development",
    "frontend development",
    "backend development",
    "full stack development",
    "react",
    "node.js",
    "django",
    "flask",
    "fastapi",
    "html css",
    "typescript",
    "javascript",
    "mobile development",
    "python programming",
    "java programming",
    "c programming",
    "c++ programming",
    "go programming",
    "rust programming",
    "sql",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "neural networks",
    "natural language processing",
    "computer vision",
    "reinforcement learning",
    "generative ai",
    "large language models",
    "transformers",
    "data science",
    "data analysis",
    "data engineering",
    "data visualization",
    "statistics",
    "probability",
    "feature engineering",
    "model evaluation",
    "mlops",
    "pandas",
    "numpy",
    "scikit-learn",
    "pytorch",
    "tensorflow",
    "huggingface",
    "langchain",
    "vector databases",
    "embeddings",
    "retrieval augmented generation",
    "prompt engineering",
    "cloud computing",
    "amazon web services",
    "microsoft azure",
    "google cloud platform",
    "kubernetes",
    "docker",
    "containers",
    "ci cd pipelines",
    "infrastructure as code",
    "terraform",
    "linux administration",
    "system design",
    "relational databases",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "database design",
    "cybersecurity",
    "network security",
    "application security",
    "cryptography",
    "ethical hacking",
    "secure coding",
    "mathematics",
    "linear algebra",
    "calculus",
    "discrete mathematics",
    "graph theory",
    "optimization",
    "physics",
    "quantum mechanics",
    "chemistry",
    "biology",
    "genetics",
    "neuroscience",
    "climate science",
    "engineering",
    "mechanical engineering",
    "electrical engineering",
    "civil engineering",
    "robotics",
    "embedded systems",
    "medicine",
    "public health",
    "business administration",
    "entrepreneurship",
    "product management",
    "project management",
    "marketing",
    "economics",
    "finance",
    "accounting",
    "user experience design",
    "user interface design",
    "graphic design",
    "design systems",
    "history",
    "philosophy",
    "psychology",
    "sociology",
    "political science",
    "law",
    "linguistics",
    "literature",
    "language learning",
    "public speaking",
    "technical writing",
    "communication skills",
    "leadership",
    "critical thinking",
    "study skills",
    "online courses",
    "tutorial",
]


_DOCUMENT_FIELDS = (
    "title",
    "topic",
    "keyword",
    "keywords",
    "summary",
    "description",
    "content",
    "body",
    "text",
)


@dataclass(frozen=True)
class RetrievedEvidence:
    """A retrieved KB document and its cosine similarity score."""

    text: str
    score: float


def _env_float(name: str, fallback: float) -> float:
    value = os.getenv(name)
    if value is None:
        return fallback
    try:
        return float(value)
    except ValueError:
        print(f"[RAG] Invalid {name}={value!r}; using {fallback}.")
        return fallback


def _env_int(name: str, fallback: int) -> int:
    value = os.getenv(name)
    if value is None:
        return fallback
    try:
        return int(value)
    except ValueError:
        print(f"[RAG] Invalid {name}={value!r}; using {fallback}.")
        return fallback


def _resolve_backend_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return _BACKEND_DIR / candidate


def _default_kb_path() -> Path:
    configured = os.getenv("RAG_KB_PATH") or os.getenv("EDUCATIONAL_KB_PATH")
    return _resolve_backend_path(configured or _DEFAULT_KB_RELATIVE_PATH)


def _default_cache_path() -> Path:
    configured = os.getenv("RAG_CACHE_PATH")
    return _resolve_backend_path(configured or _DEFAULT_CACHE_RELATIVE_PATH)


def _normalize_document(text: Any) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return normalized


def _documents_from_mapping(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in _DOCUMENT_FIELDS:
        value = item.get(field)
        if isinstance(value, list):
            parts.extend(_normalize_document(v) for v in value)
        elif isinstance(value, dict):
            parts.append(_normalize_document(json.dumps(value, sort_keys=True)))
        elif value is not None:
            parts.append(_normalize_document(value))
    return _normalize_document(" ".join(part for part in parts if part))


def _documents_from_json_payload(payload: Any) -> list[str]:
    if isinstance(payload, str):
        return [_normalize_document(payload)]

    if isinstance(payload, list):
        documents: list[str] = []
        for item in payload:
            documents.extend(_documents_from_json_payload(item))
        return documents

    if isinstance(payload, dict):
        for key in ("documents", "items", "records", "knowledge_base"):
            value = payload.get(key)
            if isinstance(value, list):
                return _documents_from_json_payload(value)
        return [_documents_from_mapping(payload)]

    return []


def _load_jsonl(path: Path) -> list[str]:
    documents: list[str] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                documents.extend(_documents_from_json_payload(json.loads(stripped)))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSONL in {path} on line {line_number}: {exc}"
                ) from exc
    return documents


def _load_json(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as file:
        return _documents_from_json_payload(json.load(file))


def _load_csv(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return [_documents_from_mapping(row) for row in reader]


def _load_text(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", raw)]
    if len(paragraphs) <= 1:
        paragraphs = [line.strip() for line in raw.splitlines()]
    return [
        _normalize_document(part)
        for part in paragraphs
        if part.strip() and not part.lstrip().startswith("#")
    ]


def _load_documents(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        documents = _load_jsonl(path)
    elif suffix == ".json":
        documents = _load_json(path)
    elif suffix == ".csv":
        documents = _load_csv(path)
    elif suffix in {".txt", ".md", ".markdown"}:
        documents = _load_text(path)
    else:
        raise ValueError(
            f"Unsupported RAG knowledge-base file type {suffix!r}. "
            "Use JSON, JSONL, CSV, TXT, or Markdown."
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for document in documents:
        normalized = _normalize_document(document)
        key = normalized.casefold()
        if normalized and key not in seen:
            deduped.append(normalized)
            seen.add(key)
    return deduped


def _documents_hash(documents: Iterable[str]) -> str:
    joined = "\n".join(documents)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def clean_text(text: str) -> str:
    """Normalize a candidate keyword without destroying technical tokens."""

    lowered = str(text or "").lower()
    lowered = re.sub(r"[^\w#+.\s-]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


class EducationalRAGFilter:
    """Retrieve educational evidence and classify candidate keyphrases."""

    def __init__(
        self,
        knowledge_base_path: str | Path | None = None,
        threshold: float | None = None,
        top_k: int | None = None,
        cache_path: str | Path | None = None,
        fallback_documents: Iterable[str] = DEFAULT_EDUCATIONAL_KB,
    ) -> None:
        self.knowledge_base_path = (
            _resolve_backend_path(knowledge_base_path)
            if knowledge_base_path is not None
            else _default_kb_path()
        )
        self.threshold = (
            threshold
            if threshold is not None
            else _env_float(
                "RAG_SIMILARITY_THRESHOLD",
                _env_float("KB_THRESHOLD", 0.45),
            )
        )
        self.top_k = top_k if top_k is not None else _env_int("RAG_TOP_K", 3)
        self.cache_path = (
            _resolve_backend_path(cache_path)
            if cache_path is not None
            else _default_cache_path()
        )
        self.fallback_documents = list(fallback_documents)
        self.documents: list[str] = self._load_corpus()
        self._embeddings: np.ndarray | None = None

    def _load_corpus(self) -> list[str]:
        if self.knowledge_base_path.exists():
            documents = _load_documents(self.knowledge_base_path)
            if documents:
                print(
                    "[RAG] Loaded "
                    f"{len(documents)} educational KB documents from "
                    f"{self.knowledge_base_path}."
                )
                return documents
            print(f"[RAG] {self.knowledge_base_path} is empty; using fallback corpus.")
        else:
            print(
                "[RAG] Knowledge base not found at "
                f"{self.knowledge_base_path}; using fallback corpus."
            )
        return list(self.fallback_documents)

    def _load_embeddings(self) -> np.ndarray:
        if self._embeddings is not None:
            return self._embeddings

        expected_hash = _documents_hash(self.documents)
        if self.cache_path.exists():
            try:
                cached = np.load(self.cache_path, allow_pickle=False)
                cached_hash = str(cached["documents_hash"][0])
                if cached_hash == expected_hash:
                    self._embeddings = cached["embeddings"]
                    return self._embeddings
            except Exception as exc:
                print(f"[RAG] Failed to load embedding cache, rebuilding: {exc}")

        self._embeddings = embed_text(self.documents)
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(
                self.cache_path,
                embeddings=self._embeddings,
                documents_hash=np.array([expected_hash]),
            )
        except Exception as exc:
            print(f"[RAG] Failed to write embedding cache: {exc}")
        return self._embeddings

    def retrieve(self, phrase: str, top_k: int | None = None) -> list[RetrievedEvidence]:
        """Return top retrieved KB evidence for ``phrase``."""

        cleaned = clean_text(phrase)
        if not cleaned:
            return []

        limit = max(1, top_k or self.top_k)
        query_vector = embed_text(cleaned)
        similarities = cosine_similarity(query_vector, self._load_embeddings())[0]
        top_indexes = similarities.argsort()[::-1][:limit]
        return [
            RetrievedEvidence(self.documents[index], float(similarities[index]))
            for index in top_indexes
        ]

    def top_matches(self, phrase: str, k: int = 3) -> list[tuple[str, float]]:
        """Compatibility API for callers that expect ``(text, score)`` tuples."""

        return [(item.text, item.score) for item in self.retrieve(phrase, top_k=k)]

    def score(self, phrase: str) -> float:
        """Return the top retrieval similarity score for ``phrase``."""

        matches = self.retrieve(phrase, top_k=1)
        return matches[0].score if matches else 0.0

    def is_educational(self, phrase: str) -> bool:
        """Return whether ``phrase`` has sufficiently strong KB evidence."""

        return self.score(phrase) >= self.threshold

    def classify(self, phrase: str) -> int:
        """Return ``1`` for educational phrases and ``0`` otherwise."""

        return 1 if self.is_educational(phrase) else 0


_rag_filter_singleton: EducationalRAGFilter | None = None


def get_rag_filter() -> EducationalRAGFilter:
    """Return the process-wide RAG filter singleton."""

    global _rag_filter_singleton
    if _rag_filter_singleton is None:
        _rag_filter_singleton = EducationalRAGFilter()
    return _rag_filter_singleton


def classify_educational_keyword(input_sentence: str) -> int:
    """Public classifier used by the recommendation pipeline."""

    return get_rag_filter().classify(input_sentence)
