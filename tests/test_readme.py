"""Tests for the visual README and the directory site's polished top."""
import json
import os

import pytest

from src.publishing.generator import DIRECTORY_CONTACT_EMAIL, generate_site

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
README = open(os.path.join(REPO_ROOT, "README.md"), encoding="utf-8").read()
DIRECTORY_TEMPLATE = open(
    os.path.join(REPO_ROOT, "templates", "directory.html"),
    encoding="utf-8").read()

LIVE_URL = "https://unaveragetech.github.io/open-project-directory/"
SUBMIT_URL = ("https://github.com/unaveragetech/open-project-directory/"
              "issues/new?template=submit-project.yml")
CONTACT = "primecomputerpieces@gmail.com"


def test_readme_has_badges_live_link_and_hero():
    assert "img.shields.io" in README
    assert LIVE_URL in README
    assert "Find verified internet projects" in README


def test_readme_has_submit_cta_and_showcase_table():
    assert SUBMIT_URL in README
    assert "Submit a project" in README
    for name in ("TokenBroker", "Collectify", "Dead Grid"):
        assert name in README
    assert "Example AI Assistant" in README
    assert "Clearly-marked example" in README


def test_readme_has_mermaid_flow_and_contact():
    assert "```mermaid" in README
    assert "flowchart" in README
    assert "Score 0–100" in README
    assert CONTACT in README
    assert "primecomputerpieces@gmail.com" in README


def test_readme_keeps_honest_labels():
    # Expedited tiers stay proposed; Adsterra confirmation still outstanding.
    assert "Proposed, not confirmed" in README
    assert "still required before deploying" in README
    assert "Illustrative assumptions only" in README


def test_directory_template_has_hero_and_footer_contact():
    assert 'class="hero"' in DIRECTORY_TEMPLATE
    assert "Find verified internet projects" in DIRECTORY_TEMPLATE
    assert SUBMIT_URL in DIRECTORY_TEMPLATE
    assert 'class="site-footer"' in DIRECTORY_TEMPLATE
    assert "directory_contact_email" in DIRECTORY_TEMPLATE


def test_generated_index_has_hero_and_footer_email(tmp_path):
    generate_site(
        os.path.join(REPO_ROOT, "data", "projects.json"),
        str(tmp_path / "site"))
    index = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert 'class="hero"' in index
    assert "Find verified internet projects" in index
    assert DIRECTORY_CONTACT_EMAIL in index
    assert SUBMIT_URL in index
    n = len(json.load(open(os.path.join(REPO_ROOT, "data", "projects.json")))["projects"])
    assert f"{n} verified projects" in index
