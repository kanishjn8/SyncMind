"""Educational keyword classifier wrapper.

The public ``classify_sentence`` API is preserved for ``main.py`` callers,
but the decision now comes from the RAG filter in ``backend/model.py``.
"""

try:
    from model import classify_educational_keyword, clean_text
except ModuleNotFoundError:  # Allows importing as ``backend.utils.data_loader``.
    from backend.model import classify_educational_keyword, clean_text


def classify_sentence(input_sentence: str) -> int:
    """Return ``1`` if ``input_sentence`` has educational KB evidence."""

    cleaned = clean_text(input_sentence)
    if not cleaned:
        return 0
    return classify_educational_keyword(cleaned)
