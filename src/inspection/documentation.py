"""Documentation extraction: README / docs / API references.

Fetches the documentation URL (and a repo README when a GitHub repo is
given) and extracts headings and feature-like lines, each tied to its
source URL. Nothing is invented: extraction only returns text actually
present on the fetched pages.
"""
import httpx
from bs4 import BeautifulSoup

from .security_inspector import check_url_safe

TIMEOUT = 15.0
USER_AGENT = "OpenProjectDirectory-Bot/1.0 (+https://unaveragetech.github.io/open-project-directory)"
MAX_BYTES = 2 * 1024 * 1024


def extract_from_html(html, source_url):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])]
    text = soup.get_text(" ", strip=True)
    return {
        "source_url": source_url,
        "headings": headings[:30],
        "text_excerpt": text[:4000],
        "word_count": len(text.split()),
    }


def fetch_documentation(doc_url, repo_url=None):
    """Return extracted docs info; every item carries its source URL."""
    results = {"documentation": None, "readme": None, "errors": []}
    for url, key in ((doc_url, "documentation"), (repo_url, "readme")):
        if not url:
            continue
        safe, reason = check_url_safe(url)
        if not safe:
            results["errors"].append(f"{key}: SSRF guard: {reason}")
            continue
        try:
            with httpx.Client(timeout=TIMEOUT, follow_redirects=True,
                              headers={"User-Agent": USER_AGENT}) as client:
                response = client.get(url)
                if response.status_code != 200:
                    results["errors"].append(f"{key}: HTTP {response.status_code}")
                    continue
                content = response.content[:MAX_BYTES]
                if "text/html" in (response.headers.get("content-type") or ""):
                    results[key] = extract_from_html(content.decode("utf-8", "ignore"), url)
                else:
                    results[key] = {"source_url": url,
                                    "text_excerpt": content.decode("utf-8", "ignore")[:4000],
                                    "word_count": len(content.split())}
        except httpx.HTTPError as exc:
            results["errors"].append(f"{key}: {exc}")
    return results
