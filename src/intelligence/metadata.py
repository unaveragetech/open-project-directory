"""Metadata normalisation: turn extracted docs into a project record.

Every normalised field records its source URL so a reviewer can verify it.
Fields with no source evidence are left empty, never invented.
"""
from ..submission.normalizer import normalize_url, slugify


def normalize_metadata(submission, doc_result):
    """Build a project record dict from a submission + doc extraction."""
    submission = submission or {}
    doc_result = doc_result or {}
    doc = doc_result.get("documentation") or {}
    record = {
        "name": (submission.get("name") or "").strip(),
        "slug": slugify(submission.get("name") or "project"),
        "website_url": normalize_url(submission.get("website") or ""),
        "documentation_url": normalize_url(submission.get("documentation") or ""),
        "repository_url": normalize_url(submission.get("repository") or ""),
        "creator": (submission.get("creator") or "").strip(),
        "description": (submission.get("description") or "").strip(),
        "category": submission.get("category") or [],
        "pricing": (submission.get("pricing") or "").strip().lower() or None,
        "open_source": bool(submission.get("open_source")),
        "sources": {
            "description": submission.get("website"),
            "documentation": doc.get("source_url"),
        },
    }
    if doc.get("headings"):
        record["doc_headings"] = doc["headings"][:10]
    return record
