"""Rotating sponsored messages: 200 unique, always disclosed, always
optional — plus the agent sub-message that following the link is never
required to reach the project."""
import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
MESSAGES_PATH = os.path.join(ROOT, "static", "js", "sponsored-messages.json")
SPONSORED_JS = os.path.join(ROOT, "static", "js", "sponsored.js")


def load_messages():
    with open(MESSAGES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def test_exactly_200_unique_messages():
    messages = load_messages()
    assert len(messages) == 200
    assert len({m["text"] for m in messages}) == 200


def test_every_message_discloses_sponsored_and_support():
    for m in load_messages():
        text = m["text"].lower()
        assert "sponsored" in text or "advertisement" in text, m["text"]
        assert "support" in text, m["text"]
        assert m["sub"], m["text"]


def test_sub_message_says_optional_never_required():
    for m in load_messages():
        sub = m["sub"].lower()
        assert "optional" in sub, m["sub"]
        assert "never required" in sub, m["sub"]
        assert "agent" in sub, m["sub"]


def test_no_message_gates_or_rewards_a_click():
    banned = ("click to continue", "to unlock", "must click",
              "reward", "earn", "get access")
    for m in load_messages():
        text = (m["text"] + " " + m["sub"]).lower()
        for phrase in banned:
            assert phrase not in text, (phrase, m["text"])


def test_templates_wire_sponsored_js_and_sub_slot():
    for template in ("project.html", "directory.html", "interstitial.html"):
        html = open(os.path.join(ROOT, "templates", template),
                    encoding="utf-8").read()
        assert "sponsored.js" in html, template
        assert 'class="sponsored-sub"' in html, template
        assert 'class="sponsored-link"' in html, template
        # Static fallback label stays in the HTML for no-JS visitors.
        assert ">Sponsored</a>" in html, template


def test_sponsored_js_loads_json_and_keeps_fallback():
    js = open(SPONSORED_JS, encoding="utf-8").read()
    assert "sponsored-messages.json" in js
    assert "Math.random" in js
    assert "sponsored-sub" in js
    assert "catch" in js  # failure keeps the static "Sponsored" text


def test_sponsored_js_captures_script_tag_up_front():
    # Regression: document.currentScript is null by the time the
    # DOMContentLoaded handler runs, so reading it inside load() made
    # the JSON fetch resolve relative to the page URL and 404 on every
    # project page — the link stayed on the static "Sponsored" text.
    # The script element must be captured while the script executes.
    js = open(SPONSORED_JS, encoding="utf-8").read()
    assert "document.currentScript" in js
    assert "scriptEl" in js
    assert "scriptEl.src" in js
    assert 'querySelector(\'script[src*="sponsored.js"]\')' in js or \
        'querySelector("script[src*=\\"sponsored.js\\"]")' in js


def test_placements_renders_sub_slot():
    from src.advertising.placements import render_sponsored_link
    html = render_sponsored_link()
    assert 'rel="sponsored noopener"' in html
    assert 'target="_blank"' in html
    assert 'class="sponsored-sub"' in html
