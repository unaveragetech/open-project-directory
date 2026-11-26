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
