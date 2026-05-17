"""Educational-topic knowledge base.

Replaces the legacy TF-IDF + Random Forest classifier in
``utils/data_loader.py``. We embed a curated set of educational concept
anchors with the same sentence-transformer model used elsewhere in the
backend, then classify a candidate phrase by cosine similarity against
its nearest anchor.

Why this exists:
- TF-IDF + RF on single tokens has almost no signal (e.g. "transformer"
  reads identical whether electrical or attention-based).
- Adding a concept becomes a one-line data change instead of a retrain.
- Reuses the embedding model we already load, no extra dependency.
- The output is a calibrated score, so the threshold is tunable.

This is retrieval-only — no LLM in the loop. RAG (with generation) is
overkill for a binary "is this educational?" filter; cosine threshold
gives the same answer cheaper and deterministically.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .vectorizer import embed_text


# Curated list of educational concept anchors, grouped by domain. Order
# does not matter; semantic similarity handles synonyms and adjacent
# vocabulary. Aim for breadth (every major academic/professional
# discipline) rather than depth — the embedding model fills in the rest.
EDUCATIONAL_CONCEPTS: list[str] = [
    # Computer science & software engineering
    "computer science", "programming", "software engineering", "algorithms",
    "data structures", "operating systems", "computer networks", "compilers",
    "computer architecture", "distributed systems", "concurrency",
    "object oriented programming", "functional programming", "design patterns",
    "version control", "git", "open source software", "code refactoring",
    "software testing", "debugging",

    # Web & mobile
    "web development", "frontend development", "backend development",
    "full stack development", "react", "next.js", "vue", "angular",
    "node.js", "express", "django", "flask", "fastapi", "spring boot",
    "html css", "tailwind css", "typescript", "javascript",
    "mobile development", "android development", "ios development",
    "flutter", "react native", "kotlin", "swift",

    # Programming languages
    "python programming", "java programming", "c programming",
    "c++ programming", "go programming", "rust programming", "ruby",
    "scala", "haskell", "sql",

    # Data, AI, ML
    "artificial intelligence", "machine learning", "deep learning",
    "neural networks", "natural language processing", "computer vision",
    "reinforcement learning", "generative ai", "large language models",
    "transformers", "attention mechanism", "diffusion models",
    "data science", "data analysis", "data engineering", "data visualization",
    "statistics", "probability", "bayesian inference", "time series analysis",
    "feature engineering", "model evaluation", "mlops",
    "pandas", "numpy", "scikit-learn", "pytorch", "tensorflow",
    "huggingface", "langchain", "vector databases", "embeddings",
    "retrieval augmented generation", "prompt engineering",

    # Cloud, DevOps, infra
    "cloud computing", "amazon web services", "microsoft azure",
    "google cloud platform", "kubernetes", "docker", "containers",
    "ci cd pipelines", "infrastructure as code", "terraform",
    "site reliability engineering", "monitoring and observability",
    "linux administration", "system design",

    # Databases
    "relational databases", "postgresql", "mysql", "mongodb", "redis",
    "database design", "sql queries", "nosql databases", "data modeling",

    # Security
    "cybersecurity", "network security", "application security",
    "cryptography", "ethical hacking", "penetration testing",
    "secure coding", "authentication and authorization", "oauth",

    # Math
    "mathematics", "linear algebra", "calculus", "discrete mathematics",
    "differential equations", "real analysis", "abstract algebra",
    "graph theory", "number theory", "optimization", "numerical methods",

    # Physical sciences
    "physics", "classical mechanics", "quantum mechanics", "quantum physics",
    "electromagnetism", "thermodynamics", "relativity", "astrophysics",
    "cosmology", "particle physics",
    "chemistry", "organic chemistry", "inorganic chemistry",
    "physical chemistry", "biochemistry",

    # Life & earth sciences
    "biology", "genetics", "molecular biology", "neuroscience",
    "ecology", "evolutionary biology", "microbiology",
    "earth science", "geology", "climate science", "meteorology",
    "astronomy",

    # Engineering disciplines
    "engineering", "mechanical engineering", "electrical engineering",
    "civil engineering", "chemical engineering", "aerospace engineering",
    "robotics", "control systems", "signal processing", "embedded systems",
    "vlsi design", "renewable energy",

    # Medicine & health
    "medicine", "anatomy", "physiology", "pharmacology", "pathology",
    "public health", "epidemiology", "nutrition", "mental health",
    "nursing", "healthcare",

    # Business, economics, finance
    "business administration", "entrepreneurship", "product management",
    "project management", "marketing", "digital marketing",
    "operations management", "supply chain management",
    "economics", "microeconomics", "macroeconomics", "behavioral economics",
    "finance", "corporate finance", "personal finance", "investing",
    "stock market", "accounting", "auditing", "taxation",

    # Design & UX
    "user experience design", "user interface design", "interaction design",
    "graphic design", "typography", "design systems", "product design",
    "design thinking",

    # Humanities & arts
    "history", "philosophy", "ethics", "logic", "psychology", "sociology",
    "anthropology", "political science", "law", "international relations",
    "linguistics", "literature", "creative writing",
    "art history", "music theory", "film studies", "photography",

    # Languages
    "english language learning", "spanish language learning",
    "french language learning", "german language learning",
    "mandarin chinese learning", "japanese language learning",
    "language learning",

    # Productivity / soft skills (still educational)
    "public speaking", "technical writing", "communication skills",
    "negotiation", "leadership", "critical thinking", "study skills",

    # Test prep / academic
    "sat preparation", "gre preparation", "gmat preparation",
    "ielts preparation", "toefl preparation", "school education",
    "online courses", "tutorial",
]


_DEFAULT_THRESHOLD = float(os.getenv("KB_THRESHOLD", "0.45"))
_CACHE_PATH = Path(__file__).resolve().parent / "kb_embeddings.npz"


def _concept_hash(concepts: list[str]) -> str:
    return hashlib.sha256("\n".join(concepts).encode("utf-8")).hexdigest()


class KnowledgeBase:
    """Embedding-based educational-topic filter."""

    def __init__(
        self,
        concepts: Iterable[str] = EDUCATIONAL_CONCEPTS,
        threshold: float = _DEFAULT_THRESHOLD,
        cache_path: Path | None = _CACHE_PATH,
    ) -> None:
        self.concepts: list[str] = list(concepts)
        self.threshold = threshold
        self.cache_path = cache_path
        self._embeddings: np.ndarray | None = None

    def _load_embeddings(self) -> np.ndarray:
        if self._embeddings is not None:
            return self._embeddings

        expected_hash = _concept_hash(self.concepts)

        if self.cache_path and self.cache_path.exists():
            try:
                cached = np.load(self.cache_path, allow_pickle=False)
                cached_hash = str(cached["concepts_hash"][0])
                if cached_hash == expected_hash:
                    self._embeddings = cached["embeddings"]
                    return self._embeddings
            except Exception as e:
                # Cache is corrupt or mismatched; we'll rebuild below.
                print(f"[KB] Failed to load cache, rebuilding: {e}")

        embeddings = embed_text(self.concepts)
        self._embeddings = embeddings
        if self.cache_path:
            try:
                np.savez(
                    self.cache_path,
                    embeddings=embeddings,
                    concepts_hash=np.array([expected_hash]),
                )
            except Exception as e:
                print(f"[KB] Failed to write cache: {e}")
        return embeddings

    def top_matches(self, phrase: str, k: int = 3) -> list[tuple[str, float]]:
        """Return the top-``k`` (concept, similarity) pairs for ``phrase``."""
        phrase = (phrase or "").strip()
        if not phrase:
            return []
        query_vec = embed_text(phrase)
        sims = cosine_similarity(query_vec, self._load_embeddings())[0]
        top_idx = sims.argsort()[::-1][:k]
        return [(self.concepts[i], float(sims[i])) for i in top_idx]

    def score(self, phrase: str) -> float:
        """Highest similarity between ``phrase`` and any concept in the KB."""
        matches = self.top_matches(phrase, k=1)
        return matches[0][1] if matches else 0.0

    def is_educational(self, phrase: str) -> bool:
        return self.score(phrase) >= self.threshold


_kb_singleton: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    """Return the process-wide ``KnowledgeBase`` singleton (lazy)."""
    global _kb_singleton
    if _kb_singleton is None:
        _kb_singleton = KnowledgeBase()
    return _kb_singleton
