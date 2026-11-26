"""Compliance tests: the Continue button must work independently of any ad click."""
import html
import json
import os
import re

from src.advertising.placements import ADSTERRA_SMARTLINK_URL
from src.publishing.generator import generate_site

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _load_projects():
    with open(os.path.join(ROOT, "data", "projects.json"), encoding="utf-8") as fh:
        return json.load(fh)["projects"]


def test_adsterra_url_is_the_issued_smartlink():
    assert ADSTERRA_SMARTLINK_URL == "https://asiafilm.org/4/f3a2a61554ddd109d393d78e61fa4202"


def test_generated_interstitials(tmp_path):
    counts = generate_site(os.path.join(ROOT, "data", "projects.json"),
                           str(tmp_path / "site"))
    assert counts["projects"] == len(json.load(open(os.path.join(ROOT, "data", "projects.json")))["projects"])
    assert counts["interstitials"] == len(json.load(open(os.path.join(ROOT, "data", "projects.json")))["projects"])
    for project in _load_projects():
        html = (tmp_path / "site" / "go" / project["slug"] / "index.html").read_text()
        # Continue link exists, points at the real project URL, not the ad.
        m = re.search(r'id="continue-btn"[^>]*href="([^"]+)"', html)
        assert m, f"no Continue button in {project['slug']}"
        assert m.group(1) == project["website_url"]
        assert m.group(1) != ADSTERRA_SMARTLINK_URL
        # Adsterra URL appears only inside a Sponsored-labelled element.
        assert ADSTERRA_SMARTLINK_URL in html
        ad_match = re.search(
            r'<a class="sponsored-link" href="' + re.escape(ADSTERRA_SMARTLINK_URL) +
            r'"[^>]*>Sponsored</a>', html)
        assert ad_match, f"ad link not labelled Sponsored in {project['slug']}"
        # No ad-click gating in the countdown script: it must never listen
        # for clicks on the ad, reference the sponsored link, or gate the
        # Continue button on an ad event. Enabling is timer-based only.
        js = (tmp_path / "site" / "static" / "js" / "interstitial.js").read_text()
        assert "sponsored-link" not in js
        assert "addEventListener" not in js or "click" not in js
        assert "setTimeout" in js  # countdown is purely time-based
        assert "continue-btn" in js


def test_generated_profiles_and_index(tmp_path):
    generate_site(os.path.join(ROOT, "data", "projects.json"), str(tmp_path / "site"))
    assert (tmp_path / "site" / "index.html").exists()
    for project in _load_projects():
        profile = tmp_path / "site" / "project" / project["slug"] / "index.html"
        assert profile.exists()
        # Names are HTML-escaped in the page ("Workman's Clock" renders
        # as "Workman&#x27;s Clock"), so unescape before comparing.
        text = html.unescape(profile.read_text())
        assert project["name"] in text
        assert project["website_url"] in text
