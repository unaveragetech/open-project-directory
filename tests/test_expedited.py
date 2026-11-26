"""Expedited review: proposed tiers in config, transaction-code rules,
and the generated expedited page (Cash App link + email + all tiers)."""
import os
import re

import yaml

from src.publishing.generator import generate_site, load_expedited_review
from src.submission.parser import parse_expedited_tier, parse_issue_body
from src.submission.validator import validate_submission

ROOT = os.path.join(os.path.dirname(__file__), "..")
CASHAPP = "https://cash.app/$slightlysigh"
EMAIL = "primecomputerpieces@gmail.com"

EXPECTED = [
    ("free", 0, "10–14 days"),
    ("standard", 5, "3–5 days"),
    ("priority", 15, "24–48 hours"),
    ("same-day", 30, "Same day if submitted before 12pm ET, otherwise next day"),
]


def _base():
    return {"name": "Example", "website": "https://example.com",
            "description": "An example.", "category": ["AI"],
            "creator": "Example Dev"}


def test_tier_config_loads():
    with open(os.path.join(ROOT, "config", "expedited_review.yml")) as fh:
        data = yaml.safe_load(fh)
    assert data["cashapp_url"] == CASHAPP
    assert data["contact_email"] == EMAIL
    tiers = {(t["key"], t["donation_usd"], t["wait_time"]) for t in data["tiers"]}
    for key, amount, wait in EXPECTED:
        assert (key, amount, wait) in tiers, f"missing tier {key}"
    assert data.get("guarantee") is False


def test_load_expedited_review_defaults():
    cfg = load_expedited_review()
    assert cfg["cashapp_url"] == CASHAPP
    assert cfg["contact_email"] == EMAIL
    assert [t["key"] for t in cfg["tiers"]] == [e[0] for e in EXPECTED]


def test_free_needs_no_transaction_code():
    ok, errors = validate_submission({**_base(), "expedited_review": "free"})
    assert ok, errors


def test_paid_tier_requires_transaction_code():
    for tier in ("standard", "priority", "same-day"):
        ok, errors = validate_submission({**_base(), "expedited_review": tier})
        assert not ok
        assert any("transaction code" in e for e in errors), errors
        ok, errors = validate_submission(
            {**_base(), "expedited_review": tier, "transaction_code": "ABC123"})
        assert ok, errors


def test_paid_tier_label_form_is_accepted_with_code():
    ok, errors = validate_submission(
        {**_base(), "expedited_review": "Priority — $15 donation (24–48 hours)",
         "transaction_code": "XYZ789"})
    assert ok, errors


def test_unknown_tier_rejected_and_bad_email_rejected():
    ok, errors = validate_submission({**_base(), "expedited_review": "express"})
    assert not ok
    ok, errors = validate_submission({**_base(), "contact_email": "not-an-email"})
    assert not ok
    ok, errors = validate_submission({**_base(), "contact_email": EMAIL})
    assert ok, errors


def test_parser_maps_expedited_fields():
    body = (
        "### Project name\nExample\n\n"
        "### Website URL\nhttps://example.com\n\n"
        "### Expedited review\nPriority — $15 donation (24–48 hours)\n\n"
        "### Transaction code\nABC123\n\n"
        "### Contact email\nprimecomputerpieces@gmail.com\n"
    )
    data = parse_issue_body(body)
    assert data["transaction_code"] == "ABC123"
    assert data["contact_email"] == EMAIL
    assert parse_expedited_tier(data["expedited_review"]) == "priority"
    assert parse_expedited_tier("Same-day — $30 donation") == "same-day"
    assert parse_expedited_tier("Free — standard queue") == "free"


def test_expedited_page_generated(tmp_path):
    site = tmp_path / "site"
    counts = generate_site(os.path.join(ROOT, "data", "projects.json"), str(site))
    assert counts["projects"] == 4
    assert counts["profiles"] == 4
    assert counts["interstitials"] == 4
    assert counts["expedited_pages"] == 1
    page = site / "expedited-review" / "index.html"
    assert page.exists()
    html = page.read_text()
    assert CASHAPP in html
    assert EMAIL in html
    for key, amount, wait in EXPECTED:
        # Tier name + wait time present; Free shows "Free", paid show $amount.
        assert wait in html, f"wait time missing for {key}"
        if amount:
            assert f"${amount}" in html
    assert "does not guarantee approval" in html.lower()
    assert "12pm ET" in html
    # Index links to it and shows the tiers.
    index = (site / "index.html").read_text()
    assert "/expedited-review/" in index
    assert CASHAPP in index
    assert EMAIL in index
    for _, amount, wait in EXPECTED:
        assert wait in index
