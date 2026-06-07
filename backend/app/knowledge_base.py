"""Compatibility wrapper for the educational RAG filter.

The active implementation lives in ``backend/model.py``. This module keeps
older imports working while avoiding a second keyword-filtering pipeline.
"""

try:
    from model import (
        DEFAULT_EDUCATIONAL_KB as EDUCATIONAL_CONCEPTS,
        EducationalRAGFilter as KnowledgeBase,
        get_rag_filter,
    )
except ModuleNotFoundError:  # Allows importing as ``backend.app.knowledge_base``.
    from backend.model import (
        DEFAULT_EDUCATIONAL_KB as EDUCATIONAL_CONCEPTS,
        EducationalRAGFilter as KnowledgeBase,
        get_rag_filter,
    )


def get_knowledge_base() -> KnowledgeBase:
    """Return the process-wide educational RAG filter."""

    return get_rag_filter()
