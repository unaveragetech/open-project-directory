from src.inspection.scoring import score_inspection, decision_for_score


def _http_ok():
    return {"http_status": 200, "dns_ok": True, "https_ok": True}


def _browser_ok():
    return {"rendered": True, "empty_page": False, "placeholder": False,
            "console_errors": []}


def _docs_ok():
    return {"documentation": {"word_count": 500, "source_url": "https://docs.example.com"}}


def _meta():
    return {"name": "Example", "website": "https://example.com",
            "description": "Does things.", "category": ["AI"],
            "creator": "Someone", "documentation": "https://docs.example.com",
            "repository": "https://github.com/example/project", "pricing": "free"}


def test_perfect_inspection_auto_approves():
    result = score_inspection(_http_ok(), _browser_ok(), _docs_ok(), _meta())
    assert result["score"] == 100
    assert result["decision"] == "auto_approve"


def test_bands():
    assert decision_for_score(85) == "auto_approve"
    assert decision_for_score(84) == "manual_review"
    assert decision_for_score(70) == "manual_review"
    assert decision_for_score(69) == "request_corrections"
    assert decision_for_score(50) == "request_corrections"
    assert decision_for_score(49) == "reject"


def test_failed_http_scores_low():
    result = score_inspection({"http_status": None, "dns_ok": False, "https_ok": False},
                              {}, {}, _meta())
    assert result["score"] < 50
    assert result["decision"] == "reject"


def test_hard_fail_overrides_high_score():
    meta = _meta()
    meta["hard_fail_flags"] = ["malware_detected"]
    result = score_inspection(_http_ok(), _browser_ok(), _docs_ok(), meta)
    assert result["decision"] == "reject"
    assert "malware_detected" in result["hard_fails"]


def test_weights_sum_to_100():
    from src.inspection.scoring import WEIGHTS
    assert sum(WEIGHTS.values()) == 100


def test_flags_do_not_zero_trust():
    # Regression: any submission flags ("Has a public API", …) used to
    # zero the trust component, costing 5 points for flagged projects.
    http = {"http_status": 200, "dns_ok": True, "https_ok": True}
    browser = {"rendered": True, "empty_page": False, "placeholder": False,
               "console_errors": []}
    docs = {"documentation": {"word_count": 500}}
    meta = {"name": "X", "website": "https://example.com",
            "description": "d", "category": ["AI"], "creator": "Jesse",
            "documentation": "https://example.com/docs",
            "repository": "https://github.com/example/x",
            "pricing": "freemium", "flags": "Has a public API"}
    result = score_inspection(http, browser, docs, meta)
    assert result["components"]["trust_consistency"] == 1.0
    assert result["score"] >= 85
    assert result["decision"] == "auto_approve"


def test_browser_uses_load_not_networkidle():
    import pathlib
    src = pathlib.Path(__file__).parent.parent.joinpath(
        "src", "inspection", "browser_inspector.py").read_text()
    assert 'wait_until="load"' in src
    assert 'wait_until="networkidle"' not in src


def test_bot_challenge_uses_http_content():
    # Regression from TokenBroker issue #2: Cloudflare showed the
    # browser "Just a moment…", so content/functionality scored 0 even
    # though the site is real (206 words via plain HTTP).
    from src.inspection.browser_inspector import is_bot_challenge
    assert is_bot_challenge("Just a moment...", "Checking your browser")
    assert not is_bot_challenge("TokenBroker", "One API key. Every model.")
    http = {"http_status": 200, "dns_ok": True, "https_ok": True}
    browser = {"rendered": False, "empty_page": False, "placeholder": False,
               "console_errors": ["e1", "e2"], "bot_challenge": True,
               "http_content_words": 206}
    docs = {"documentation": {"word_count": 512}}
    meta = {"name": "TokenBroker", "website": "https://tokenbroker.org",
            "description": "d", "category": ["AI", "Developer Tools"],
            "creator": "Jesse",
            "documentation": "https://unaveragetech.github.io/tokenbroker-docs/",
            "pricing": "freemium", "flags": "Has a public API"}
    result = score_inspection(http, browser, docs, meta)
    assert result["components"]["content_quality"] == 1.0
    assert result["components"]["functionality"] == 0.5
    assert result["score"] >= 85
    assert result["decision"] == "auto_approve"
