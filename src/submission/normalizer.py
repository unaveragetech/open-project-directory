"""Normalise a validated submission: URLs, slug, duplicates."""
import re
import unicodedata
from urllib.parse import urlparse, urlunparse


def normalize_url(url):
    """Lowercase scheme/host, strip trailing slash and fragments."""
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or ""
    return urlunparse((parsed.scheme.lower(), netloc, path, "", parsed.query, ""))


def slugify(name):
    text = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "project"


def normalize_submission(data):
    out = dict(data or {})
    for field in ("website", "documentation", "repository"):
        if out.get(field):
            out[field] = normalize_url(out[field])
    if out.get("name"):
        out["slug"] = slugify(out["name"])
    if isinstance(out.get("category"), str):
        out["category"] = [c.strip() for c in out["category"].split(",") if c.strip()]
    # Tags: comma-separated string or list -> slugified, deduped, in order.
    raw_tags = out.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    seen = set()
    out["tags"] = []
    for tag in raw_tags:
        slug = slugify(str(tag))
        if slug and slug not in seen:
            seen.add(slug)
            out["tags"].append(slug)
    return out


def find_duplicate(submission, existing_projects):
    """Return the existing project matching website host+path or slug, else None."""
    website = (submission.get("website") or "").lower().rstrip("/")
    slug = submission.get("slug")
    for project in existing_projects or []:
        existing_url = (project.get("website_url") or project.get("website") or "").lower().rstrip("/")
        if website and website == existing_url:
            return project
        if slug and slug == project.get("slug"):
            return project
    return None
