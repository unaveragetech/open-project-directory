"""LLM-assisted summarisation — with a strict no-invention rule.

The summariser may rephrase extracted text, but every claim in the output
must trace to a supplied source excerpt. If no LLM is configured, the
extractive fallback returns the first sentences of the source text.
"""
from .extractor import extract_features


def summarize(text, source_url, max_chars=500):
    """Extractive fallback summary: first sentences of the source text."""
    if not text:
        return {"summary": "", "source_url": source_url, "method": "extractive"}
    summary = text.strip().replace("\\n", " ")[:max_chars]
    return {"summary": summary, "source_url": source_url, "method": "extractive"}


def summarize_with_llm(text, source_url, llm_client=None):
    """Summarise via an LLM client if given, else the extractive fallback.

    llm_client must expose complete(prompt) -> str. The prompt instructs
    the model to use only the supplied text and to cite the source URL.
    The caller must verify the output against the source before publishing.
    """
    if llm_client is None:
        return summarize(text, source_url)
    prompt = (
        "Summarise the project described below in at most 3 sentences. "
        "Use ONLY information present in the text. Do not invent features, "
        "pricing, platforms, or capabilities. If something is not stated, "
        f"say so. Source: {source_url}\n\n{text[:6000]}"
    )
    output = llm_client.complete(prompt)
    return {"summary": output.strip(), "source_url": source_url, "method": "llm",
            "features": extract_features(text, source_url)}
