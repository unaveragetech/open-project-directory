"""Feature extraction from fetched documentation text.

Extractive only: returns sentences/phrases actually present in the source
text, each with its source URL. The LLM summariser (summarizer.py) may
rephrase, but must never add a capability with no source evidence.
"""
import re

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
FEATURE_KEYWORDS = (
    "free", "open source", "api", "offline", "no account", "windows",
    "linux", "macos", "android", "ios", "web", "pricing", "download",
)


def extract_features(text, source_url, max_features=10):
    """Return up to max_features source sentences mentioning feature keywords."""
    if not text:
        return []
    features = []
    for sentence in SENTENCE_RE.split(text):
        sentence = sentence.strip()
        lowered = sentence.lower()
        if 20 <= len(sentence) <= 300 and any(k in lowered for k in FEATURE_KEYWORDS):
            features.append({"text": sentence, "source_url": source_url})
        if len(features) >= max_features:
            break
    return features
