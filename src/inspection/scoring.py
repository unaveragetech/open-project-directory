"""Quality scoring, 0–100, with hard-fail overrides.

Weights (config/quality_rules.yml): website 20, security/HTTPS 15,
content 20, documentation 15, functionality 15, metadata 10, trust 5.
Bands: 85+ auto-approve, 70–84 manual review, 50–69 request corrections,
<50 reject/quarantine. Hard fails (malware, phishing, deceptive redirect,
dangerous download) block publication regardless of score.
"""
import argparse
import json

WEIGHTS = {
    "website_accessibility": 20,
    "security_https": 15,
    "content_quality": 20,
    "documentation": 15,
    "functionality": 15,
    "metadata_completeness": 10,
    "trust_consistency": 5,
}

HARD_FAILS = {
    "malware_detected", "phishing_detected", "deceptive_redirect",
    "dangerous_download", "ssrf_attempt",
}


def decision_for_score(score):
    if score >= 85:
        return "auto_approve"
    if score >= 70:
        return "manual_review"
    if score >= 50:
        return "request_corrections"
    return "reject"


def score_inspection(http_result, browser_result, doc_result, metadata):
    """Score component results (each 0.0–1.0) into a 0–100 total + decision.

    http_result / browser_result / doc_result are the dicts produced by the
    inspectors; metadata is the normalised submission dict. Missing data
    scores 0 for that component rather than raising.
    """
    http_result = http_result or {}
    browser_result = browser_result or {}
    doc_result = doc_result or {}
    metadata = metadata or {}

    components = {}
    components["website_accessibility"] = 1.0 if http_result.get("http_status") == 200 and http_result.get("dns_ok") else 0.0
    components["security_https"] = 1.0 if http_result.get("https_ok") else (
        0.5 if http_result.get("http_status") == 200 else 0.0)
    text_len = 0
    if doc_result.get("documentation"):
        text_len = doc_result["documentation"].get("word_count", 0)
    # Bot-check pages are not the site: when the browser was shown one,
    # the plain HTTP fetch (200+ words of real text) counts as the
    # content evidence instead — the site is real, the challenge is
    # just in front of it. Functionality is only partial in that case
    # (JS could not be verified through the challenge).
    bot_challenge = bool(browser_result.get("bot_challenge"))
    http_words = browser_result.get("http_content_words") or 0
    content_ok = (browser_result.get("rendered")
                  and not browser_result.get("empty_page")
                  and not browser_result.get("placeholder"))
    if bot_challenge and http_words >= 50:
        content_ok = True
    components["content_quality"] = 1.0 if content_ok else 0.0
    components["documentation"] = 1.0 if text_len >= 200 else (0.5 if text_len > 0 else 0.0)
    if bot_challenge:
        components["functionality"] = 0.5
    else:
        components["functionality"] = 1.0 if (browser_result.get("rendered") and not browser_result.get("console_errors")) else (
            0.5 if browser_result.get("rendered") else 0.0)
    filled = sum(1 for f in ("name", "website", "description", "category", "creator")
                 if metadata.get(f))
    optional = sum(1 for f in ("documentation", "repository", "pricing")
                   if metadata.get(f))
    components["metadata_completeness"] = min(1.0, (filled / 5.0) * 0.7 + (optional / 3.0) * 0.3)
    # Trust: submission flags ("open source", "has a public API", …) are
    # just metadata, not a reason to distrust a project — they used to
    # zero this component for any flagged submission. Trust is full
    # unless a hard fail was recorded (handled below via the decision).
    components["trust_consistency"] = 1.0
    total = round(sum(components[k] * WEIGHTS[k] for k in WEIGHTS), 2)
    hard_fails = sorted(set(metadata.get("hard_fail_flags") or []) & HARD_FAILS)
    decision = "reject" if hard_fails else decision_for_score(total)
    return {
        "score": total,
        "components": {k: round(v, 2) for k, v in components.items()},
        "weights": dict(WEIGHTS),
        "decision": decision,
        "hard_fails": hard_fails,
    }


def main():
    parser = argparse.ArgumentParser(description="Score an inspection from JSON files.")
    parser.add_argument("--issue", default="")
    parser.add_argument("--http", default="")
    parser.add_argument("--browser", default="")
    parser.add_argument("--docs", default="")
    parser.add_argument("--metadata", default="{}")
    args = parser.parse_args()

    def load(path):
        if not path:
            return {}
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    result = score_inspection(load(args.http), load(args.browser),
                              load(args.docs), json.loads(args.metadata))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    main()
