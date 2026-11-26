"""For Agents page + catalog.json: raw HTTPS discovery for agents, with
the rule that the ads are not to be circumvented."""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)


def _build(tmp):
    from src.publishing.generator import generate_site
    out = os.path.join(tmp, "site")
    counts = generate_site(os.path.join(ROOT, "data", "projects.json"),
                           out, base_path="/open-project-directory")
    return out, counts


def test_agents_page_and_catalog_generated():
    with tempfile.TemporaryDirectory() as tmp:
        out, counts = _build(tmp)
        assert counts["agents_pages"] == 1
        assert counts["catalog"] == 1
        agents = open(os.path.join(out, "agents", "index.html"),
                      encoding="utf-8").read()
        assert "catalog.json" in agents
        assert "/project/&lt;slug&gt;/" in agents or "/project/<slug>/" in agents
        assert "raw" in agents.lower()
        # The ad rule is stated plainly.
        assert "don't circumvent the ads" in agents.lower()
        assert "Don't strip, hide, block, or bypass the ad slots" in agents
        assert "Don't click them at scale" in agents
        assert "optional and never required" in agents
        # Catalog JSON matches the catalog.
        catalog = json.load(open(os.path.join(out, "catalog.json"),
                                 encoding="utf-8"))
        projects = json.load(open(os.path.join(ROOT, "data", "projects.json"),
                                  encoding="utf-8"))["projects"]
        assert catalog["project_count"] == len(projects)
        assert len(catalog["projects"]) == len(projects)
        for entry, project in zip(catalog["projects"], projects):
            assert entry["slug"] == project["slug"]
            assert entry["website_url"] == project["website_url"]
            assert entry["profile_url"].endswith(f"/project/{project['slug']}/")
            for key in ("name", "description", "category", "tags",
                        "pricing", "creator", "quality_score"):
                assert key in entry
        # No leaked name in the generated agents page or catalog.
        assert "llew" not in agents.lower()
        assert "llew" not in json.dumps(catalog).lower()


def test_directory_links_to_agents_page():
    with tempfile.TemporaryDirectory() as tmp:
        out, _ = _build(tmp)
        index = open(os.path.join(out, "index.html"), encoding="utf-8").read()
        assert "/agents/" in index
