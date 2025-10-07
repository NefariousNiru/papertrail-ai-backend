# util/functions.py
def clip_words(text: str, max_words: int = 100) -> str:
    """
    - Trim 'text' to at most `max_words` tokens separated by whitespace.
    - Adds an ellipsis when trimming occurs.
    """
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " …"


def stream_merge_saved(merged, saved):
    merged["verdict"] = saved.verdict
    merged["confidence"] = saved.confidence
    merged["reasoningMd"] = saved.reasoningMd
    merged["sourceUploaded"] = True
    if saved.evidence:
        merged["evidence"] = [e.model_dump(exclude_none=True) for e in saved.evidence]
