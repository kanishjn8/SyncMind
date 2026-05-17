"""Educational-topic classifier (semantic).

This module used to be a TF-IDF + Random Forest model with hard-coded
escape hatches for common terms (``ai``, ``neural network``,
``engineering``). It's now a thin wrapper around the embedding-based
knowledge base in :mod:`app.knowledge_base`.

The legacy ``random_forest_model2.pkl`` / ``vectorizer2.pkl`` files are
no longer loaded, which silences the ``InconsistentVersionWarning``
chatter at startup and lets us drop the hard-coded biases entirely:
synonyms like "AI", "artificial intelligence", or "neural networks" all
match anchors in the knowledge base via cosine similarity.

The public ``classify_sentence`` API is preserved so existing callers
in ``main.py`` keep working.
"""

import re

from app.knowledge_base import get_knowledge_base


def clean_text(text: str) -> str:
    """Lowercase and strip punctuation while preserving digits.

    Digits matter for terms like ``c++`` (becomes ``c``), ``html5``,
    ``web3`` etc. The previous version stripped digits, which made
    those terms harder to match.
    """
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def classify_sentence(input_sentence: str) -> int:
    """Return ``1`` if ``input_sentence`` looks educational, else ``0``.

    The decision is made by cosine similarity against a curated knowledge
    base of educational concept anchors. Unlike the previous classifier,
    this works equally well for short single-word inputs and multi-word
    phrases — there is no need to split a phrase before calling.
    """
    cleaned = clean_text(input_sentence)
    if not cleaned:
        return 0
    return 1 if get_knowledge_base().is_educational(cleaned) else 0
