"""Tags + search: every project has its own profile + interstitial page,
the index has a working tag search (chips, ?tag= deep links, result count,
empty state), and tags are real, slugified values in the seed data."""
import json
import os
import re

from src.publishing.generator import generate_site
from src.submission.normalizer import normalize_submission

ROOT = os.path.join(os.path.dirname(__file__), "..")
ADSTERRA = "https://asiafilm.org/4/675577d5711a79f686def97bac8e688f"


def _projects():
    with open(os.path.join(ROOT, "data", "projects.json"), encoding="utf-8") as fh:
        return json.load(fh)["projects"]


def test_seed_projects_have_real_tags():
    for p in _projects():
        tags = p.get("tags") or []
        assert tags, f"{p['slug']} has no tags"
        for t in tags:
            assert re.fullmatch(r"[a-z0-9][a-z0-9-]*", t), f"bad tag {t!r} in {p['slug']}"


def test_every_project_has_profile_and_interstitial(tmp_path):
    site = tmp_path / "site"
    generate_site(os.path.join(ROOT, "data", "projects.json"), str(site))
    assert (site / ".nojekyll").exists()
    for p in _projects():
        profile = site / "project" / p["slug"] / "index.html"
        go = site / "go" / p["slug"] / "index.html"
        assert profile.exists(), f"missing profile page for {p['slug']}"
        assert go.exists(), f"missing interstitial for {p['slug']}"
        import html as _html
        text = _html.unescape(profile.read_text())
        # Full separate page: name, description, tags, destination, docs,
        # pricing, verification status, last checked, Sponsored once.
        assert p["name"] in text
        assert p["description"] in text
        assert p["website_url"] in text
        assert p["pricing"] in text
        assert p["last_verified"] in text
        assert str(p["quality_score"]) in text
        assert text.count(ADSTERRA) == 1
        for t in p["tags"]:
            assert f"?tag={t}" in text, f"tag link ?tag={t} missing in {p['slug']}"
        # Visit button goes via the interstitial, not straight to the site.
        assert f"/go/{p['slug']}/" in text
        # Interstitial Continue still points at the real URL, not the ad.
        go_text = go.read_text()
        m = re.search(r'id="continue-btn"[^>]*href="([^"]+)"', go_text)
        assert m and m.group(1) == p["website_url"]


def test_index_has_tag_chips_count_and_empty_state(tmp_path):
    site = tmp_path / "site"
    generate_site(os.path.join(ROOT, "data", "projects.json"), str(site))
    html = (site / "index.html").read_text()
    all_tags = sorted({t for p in _projects() for t in p["tags"]})
    assert all_tags
    for t in all_tags:
        assert f'data-tag="{t}"' in html, f"no tag chip for {t}"
        assert f'href="/open-project-directory/?tag={t}"' in html or f'?tag={t}' in html
    assert 'id="result-count"' in html
    assert 'id="empty-state"' in html
    assert "no projects match" in html.lower()
    assert 'id="search"' in html
    # Every card carries its tags for the live filter.
    for p in _projects():
        assert f'data-tags="{" ".join(p["tags"])}"' in html


def test_index_links_use_pages_base_path(tmp_path):
    site = tmp_path / "site"
    generate_site(os.path.join(ROOT, "data", "projects.json"), str(site))
    for rel in ["index.html", "project/collectify/index.html",
                "go/collectify/index.html"]:
        html = (site / rel).read_text()
        assert 'href="/static/' not in html and 'src="/static/' not in html
        assert 'href="/project/' not in html and 'href="/go/' not in html
        assert 'href="/"' not in html
    assert "/open-project-directory/static/css/main.css" in (site / "index.html").read_text()


def test_directory_js_tag_search_behaviour():
    js = open(os.path.join(ROOT, "static", "js", "directory.js")).read()
    # Deep link from project pages, multi-tag, count, empty state.
    assert "URLSearchParams" in js
    assert 'params.get("tag")' in js or "get(\"tags\")" in js
    assert "selectedTags" in js
    assert "result-count" in js
    assert "empty-state" in js
    assert "aria-pressed" in js
    # Search must consider tags, not just visible text.
    assert "data-tags" in js or "dataset.tags" in js


def test_normalizer_slugifies_tags():
    out = normalize_submission({
        "name": "X", "website": "https://x.example", "category": "AI",
        "tags": "AI Tools,  api-gateway, AI Tools",
    })
    assert out["tags"] == ["ai-tools", "api-gateway"]
