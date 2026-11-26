"""End-to-end submission pipeline for the Open Project Directory.

One GitHub issue is one submission. This module drives the whole visible
lifecycle, reusing the existing parser / validator / normalizer /
inspection / scoring / generator code — it adds no second copy of that
logic:

  1. parse + validate the issue body          -> acceptance comment, or an
     invalid comment listing exactly what is missing/wrong
  2. duplicate check against data/projects.json
  3. live inspection (HTTP/TLS, headless browser, documentation)
     -> pending-review comment, then a detailed inspection comment with
        the 0-100 score breakdown per category and the decision band
  4. decision:
     - auto-approve (85+): project is added to data/projects.json and the
       outcome is ``publish``; the workflow then commits the catalog
       change, builds and deploys the site in this same run (a
       GITHUB_TOKEN push does not trigger the separate publishing
       workflow), and runs the ``finalize`` phase, which posts the live
       profile URL, labels the issue ``published`` and closes it
     - manual review (70-84): label ``needs-review``, issue stays OPEN
     - request corrections (50-69) / reject (<50) / hard fail: detailed
       denial comment, label ``failed``, issue CLOSED
     - duplicate: already-listed comment with the live URL, label
       ``published``, issue CLOSED — never a duplicate entry

Labels used (from the project outline): submitted, queued, inspecting,
passed, failed, needs-review, published, suspended.

The GitHub API client here uses only the standard library so the pipeline
has no new dependencies. In tests, pass a fake client with the same
methods (get_issue / comment_issue / add_labels / remove_label /
close_issue) and a fake inspect function.
"""
import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

# Imported lazily inside functions where the Playwright/browser path is
# involved, so importing this module never needs a browser installed.
from ..inspection.scoring import WEIGHTS, decision_for_score, score_inspection
from ..submission.normalizer import find_duplicate, normalize_submission, slugify
from ..submission.parser import (
    parse_categories,
    parse_expedited_tier,
    parse_issue_body,
    parse_links,
)
from ..submission.validator import validate_submission

REPO = "unaveragetech/open-project-directory"
DIRECTORY_URL = "https://unaveragetech.github.io/open-project-directory/"
BASE_PATH = "/open-project-directory"
CONTACT_EMAIL = "primecomputerpieces@gmail.com"

DECISION_BANDS = {
    "auto_approve": "85–100 · automatic approval",
    "manual_review": "70–84 · approval with warnings / manual review",
    "request_corrections": "50–69 · request corrections",
    "reject": "below 50 · reject / quarantine",
}

# outcome -> (label to add, close the issue?, publish the project?)
OUTCOME_MAP = {
    "publish": ("published", True, True),
    "manual_review": ("needs-review", False, False),
    "denied": ("failed", True, False),
    "invalid": ("failed", True, False),
    "duplicate": ("published", True, False),
}


def profile_url(slug):
    return f"{DIRECTORY_URL}project/{slug}/"


def go_url(slug):
    return f"{DIRECTORY_URL}go/{slug}/"


def band_text(decision):
    return DECISION_BANDS.get(decision, decision)


# ---------------------------------------------------------------------------
# Comment builders (pure functions — unit-tested, no GitHub calls)
# ---------------------------------------------------------------------------

def _fields_table(submission):
    rows = [
        ("Project", submission.get("name") or "—"),
        ("Website", submission.get("website") or "—"),
        ("Creator", submission.get("creator") or "—"),
        ("Categories", ", ".join(submission.get("category") or []) or "—"),
        ("Pricing", submission.get("pricing") or "not stated"),
        ("Documentation", submission.get("documentation") or "—"),
        ("Repository", submission.get("repository") or "—"),
        ("Expedited review", submission.get("expedited_review") or "Free (standard queue)"),
    ]
    lines = ["| Field | Value |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in rows]
    return "\n".join(lines)


def build_acceptance_comment(submission, pricing_defaulted=False):
    body = [
        "## ✅ Submission accepted — queued for inspection",
        "",
        f"Thanks for submitting **{submission.get('name', 'your project')}**! "
        "The submission was received and passed validation, so it is now "
        "queued for automated inspection.",
        "",
        _fields_table(submission),
        "",
    ]
    if pricing_defaulted:
        body += [
            "> Pricing was not stated in the submission, so the listing will "
            "show **freemium** until the creator says otherwise — reply on "
            "this issue to correct it.",
            "",
        ]
    body += [
        "### What happens next",
        "",
        "1. 🔍 **Inspection** — DNS, HTTP/TLS, redirects and headers, a "
        "headless-browser render, and a documentation check.",
        "2. 📋 **Scoring** — a 0–100 quality score with the full breakdown "
        "posted here.",
        "3. 🚀 **Publish or deny** — passing projects are added to the "
        "directory and this issue is closed with the `published` label; "
        "failing submissions get a comment explaining exactly why, the "
        "`failed` label, and this issue is closed.",
        "",
        f"Browse the directory while you wait: {DIRECTORY_URL}",
        f"Questions? Email {CONTACT_EMAIL}.",
    ]
    return "\n".join(body)


def build_invalid_comment(errors):
    lines = [
        "## ❌ Submission needs fixes before review",
        "",
        "This submission could not be accepted because of the problems "
        "below. Fix them and submit a new issue — this one is being closed "
        "with the `failed` label.",
        "",
    ]
    lines += [f"- {err}" for err in errors]
    lines += [
        "",
        "### How to fix it",
        "",
        "- Fill in every required field: **Project name, Website URL, "
        "Description, Category, Creator**.",
        "- The website must be a valid `https://` URL.",
        "- Paid expedited-review tiers need a Cash App transaction code.",
        f"- Questions? Email {CONTACT_EMAIL}.",
    ]
    return "\n".join(lines)


def build_pending_comment(submission):
    return "\n".join([
        "## 🔍 Inspection running — pending review",
        "",
        f"Inspecting **{submission.get('name', 'your project')}** "
        f"({submission.get('website', '')}):",
        "",
        "- DNS, HTTP status, TLS certificate, redirects and security headers",
        "- Headless-browser render (JavaScript errors, broken images/links, "
        "empty or placeholder pages, mobile viewport)",
        "- Documentation / README check",
        "",
        "The full score breakdown will be posted here when inspection "
        "finishes. No action is needed from you right now.",
    ])


def _score_table(score_result):
    lines = [
        "| Category | Weight | Score | Points |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key, weight in WEIGHTS.items():
        component = score_result["components"].get(key, 0.0)
        label = key.replace("_", " ").title()
        lines.append(f"| {label} | {weight} | {component:.2f} | "
                     f"{component * weight:.2f} |")
    lines.append(f"| **Total** | **100** |  | **{score_result['score']:.2f}** |")
    return "\n".join(lines)


def build_inspection_comment(submission, http_result, browser_result,
                             doc_result, score_result):
    http_result = http_result or {}
    browser_result = browser_result or {}
    doc_result = doc_result or {}
    score = score_result["score"]
    decision = score_result["decision"]
    lines = [
        "## 📋 Inspection results",
        "",
        f"**{submission.get('name', 'your project')}** scored "
        f"**{score:.2f}/100** — {band_text(decision)} "
        f"(`{decision}`).",
        "",
        _score_table(score_result),
        "",
        "### Findings",
        "",
        f"- HTTP: status `{http_result.get('http_status')}`, "
        f"DNS {'✅' if http_result.get('dns_ok') else '❌'}, "
        f"HTTPS {'✅' if http_result.get('https_ok') else '❌'}"
        + (f", TLS {http_result.get('tls_version')}"
           if http_result.get("tls_version") else ""),
        f"- Final URL: {http_result.get('final_url') or http_result.get('url') or '—'}",
    ]
    missing = http_result.get("missing_security_headers") or []
    if missing:
        lines.append(f"- Missing security headers: {', '.join(missing)}")
    if http_result.get("robots_txt"):
        lines.append("- robots.txt: found")
    if http_result.get("sitemap"):
        lines.append("- sitemap.xml: found")
    for err in http_result.get("errors") or []:
        lines.append(f"- HTTP error: {err}")
    lines += [
        f"- Browser render: {'✅ rendered' if browser_result.get('rendered') else '❌ not rendered'}"
        + (f" — “{browser_result.get('title')}”" if browser_result.get("title") else ""),
        f"- Empty page: {'yes' if browser_result.get('empty_page') else 'no'} · "
        f"Placeholder page: {'yes' if browser_result.get('placeholder') else 'no'} · "
        f"Mobile viewport: {'✅' if browser_result.get('mobile_ok') else '❌'}",
        f"- Console errors: {len(browser_result.get('console_errors') or [])} · "
        f"Broken images: {len(browser_result.get('broken_images') or [])} · "
        f"Broken links: {len(browser_result.get('broken_links') or [])}",
    ]
    if browser_result.get("bot_challenge"):
        lines.append(
            f"- ⚠️ Bot-check page: the browser was shown a bot-check "
            f"(“{browser_result.get('title', '')}”); content was verified "
            f"from the plain HTTP fetch instead "
            f"({browser_result.get('http_content_words', 0)} words). "
            f"Functionality is scored partial — JavaScript could not be "
            f"verified through the challenge.")
    for err in browser_result.get("errors") or []:
        lines.append(f"- Browser error: {err}")
    doc = doc_result.get("documentation") or {}
    if doc:
        lines.append(
            f"- Documentation: {doc.get('word_count', 0)} words from "
            f"{doc.get('source_url', '')}")
    for err in doc_result.get("errors") or []:
        lines.append(f"- Documentation error: {err}")
    hard_fails = score_result.get("hard_fails") or []
    if hard_fails:
        lines += [
            "",
            "### ⛔ Hard fails (block publication regardless of score)",
            "",
        ]
        lines += [f"- `{flag}`" for flag in hard_fails]
    lines += [
        "",
        "A passing score is a technical quality signal, not an absolute "
        "guarantee that a service is trustworthy.",
    ]
    return "\n".join(lines)


def build_denied_comment(submission, score_result, reasons, corrections=None):
    lines = [
        "## ❌ Submission denied",
        "",
        f"**{submission.get('name', 'your project')}** was not published. "
        "This issue is being closed with the `failed` label.",
        "",
        "### Why it failed",
        "",
    ]
    lines += [f"- {reason}" for reason in reasons]
    if score_result is not None:
        lines += [
            "",
            f"Quality score: **{score_result['score']:.2f}/100** — "
            f"{band_text(score_result['decision'])} "
            f"(`{score_result['decision']}`).",
        ]
        if score_result.get("hard_fails"):
            lines.append(
                "Hard fails: " + ", ".join(
                    f"`{f}`" for f in score_result["hard_fails"]))
    if corrections:
        lines += ["", "### What to fix before resubmitting", ""]
        lines += [f"- {item}" for item in corrections]
    lines += [
        "",
        "Fix the problems above and submit a new issue — a new submission "
        "goes through the same inspection and scoring.",
        f"Questions? Email {CONTACT_EMAIL}.",
    ]
    return "\n".join(lines)


def build_manual_review_comment(submission, score_result):
    return "\n".join([
        "## 👀 Manual review needed",
        "",
        f"**{submission.get('name', 'your project')}** scored "
        f"**{score_result['score']:.2f}/100** — {band_text('manual_review')}.",
        "",
        "That is below the 85-point automatic-approval bar, so a human "
        "reviewer needs to look at the inspection results above before "
        "this can be published. This issue stays **open** with the "
        "`needs-review` label until then — no action is needed from you "
        "right now.",
        f"Questions? Email {CONTACT_EMAIL}.",
    ])


def build_duplicate_comment(existing, score_result=None):
    slug = existing.get("slug", "")
    lines = [
        "## ℹ️ Already listed",
        "",
        f"**{existing.get('name', 'this project')}** is already in the "
        "directory, so no duplicate entry was added.",
        "",
        f"- 📄 Live profile: {profile_url(slug)}",
        f"- 🌐 Directory: {DIRECTORY_URL}",
        f"- 🔗 Website: {existing.get('website_url', '')}",
        "",
    ]
    if score_result is not None:
        lines.append(
            "This submission was still inspected as a re-verification: "
            f"score **{score_result['score']:.2f}/100** "
            f"(`{score_result['decision']}`). The existing listing was "
            "left unchanged.")
        lines.append("")
    lines.append(
        "This issue is being closed with the `published` label. If the "
        "existing listing needs a correction, open a new issue or email "
        f"{CONTACT_EMAIL}.")
    return "\n".join(lines)


def build_published_comment(project, score_result=None):
    slug = project["slug"]
    lines = [
        "## 🎉 Published!",
        "",
        f"**{project['name']}** is now live in the Open Project Directory:",
        "",
        f"- 📄 Profile: {profile_url(slug)}",
        f"- 🌐 Directory: {DIRECTORY_URL}",
        f"- ➡️ Visit (via the directory interstitial): {go_url(slug)}",
        "",
    ]
    if score_result is not None:
        lines.append(
            f"Quality score: **{score_result['score']:.2f}/100** "
            f"(`{score_result['decision']}`).")
        lines.append("")
    lines.append(
        "This issue is being closed with the `published` label. Thanks for "
        "submitting!")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Submission -> catalog project (no invented features)
# ---------------------------------------------------------------------------

def submission_to_project(submission, score_result, today=None,
                          https_verified=False):
    """Map a normalised, approved submission to a projects.json entry.

    Features are NOT invented: the entry carries an empty feature list —
    features may only be added later from a documented source URL.
    """
    today = today or datetime.date.today().isoformat()
    flags = str(submission.get("flags") or "").lower()
    open_source = "open source" in flags
    has_api = "has a public api" in flags
    pricing = (submission.get("pricing") or "").strip().lower()
    pricing_defaulted = not pricing
    if pricing_defaulted:
        pricing = "open-source-free" if open_source else "freemium"
    categories = submission.get("category") or []
    tags = [slugify(c) for c in categories]
    if has_api and "api" not in tags:
        tags.append("api")
    if open_source and "open-source" not in tags:
        tags.append("open-source")
    source_urls = [submission["website"]]
    if submission.get("documentation"):
        source_urls.append(submission["documentation"])
    project = {
        "name": submission["name"],
        "slug": submission["slug"],
        "website_url": submission["website"],
        "documentation_url": submission.get("documentation") or "",
        "repository_url": submission.get("repository") or "",
        "creator": submission["creator"],
        "description": submission["description"],
        "category": categories,
        "pricing": pricing,
        "open_source": open_source,
        "platforms": ["web"],
        "features": [],
        "status": "Operational",
        "https_verified": bool(https_verified),
        "quality_score": int(round(score_result["score"])) if score_result else 0,
        "last_verified": today,
        "source_urls": source_urls,
        "tags": tags,
    }
    return project, pricing_defaulted


def load_catalog(data_path):
    with open(data_path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data


def add_project_to_catalog(data_path, project):
    """Append project unless a duplicate exists. Returns (added, duplicate)."""
    data = load_catalog(data_path)
    projects = data.get("projects", [])
    duplicate = find_duplicate(
        {"website": project["website_url"], "slug": project["slug"]}, projects)
    if duplicate:
        return False, duplicate
    projects.append(project)
    data["projects"] = projects
    with open(data_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    return True, None


# ---------------------------------------------------------------------------
# Live inspection (real network + browser), with graceful degradation
# ---------------------------------------------------------------------------

def run_inspection(submission):
    """Run HTTP + browser + documentation inspection, then score it.

    Any inspector that raises is degraded to an empty result instead of
    crashing the pipeline, so the score reflects the failure honestly.
    """
    from ..inspection.browser_inspector import inspect_in_browser
    from ..inspection.documentation import fetch_documentation
    from ..inspection.http_inspector import inspect_url

    url = submission["website"]
    hard_fail_flags = []
    try:
        http_result = inspect_url(url)
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        http_result = {"url": url, "dns_ok": False, "https_ok": False,
                       "http_status": None, "errors": [str(exc)]}
    if any("SSRF guard" in str(e) for e in http_result.get("errors") or []):
        hard_fail_flags.append("ssrf_attempt")
    try:
        browser_result = inspect_in_browser(url)
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        browser_result = {"url": url, "rendered": False,
                          "console_errors": [], "broken_images": [],
                          "broken_links": [], "empty_page": True,
                          "placeholder": False, "errors": [str(exc)]}
    try:
        doc_result = fetch_documentation(
            submission.get("documentation") or "",
            submission.get("repository") or "")
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        doc_result = {"documentation": None, "readme": None,
                      "errors": [str(exc)]}
    metadata = dict(submission)
    if hard_fail_flags:
        metadata["hard_fail_flags"] = hard_fail_flags
    score_result = score_inspection(http_result, browser_result,
                                    doc_result, metadata)
    return http_result, browser_result, doc_result, score_result


# ---------------------------------------------------------------------------
# GitHub API client (standard library only)
# ---------------------------------------------------------------------------

class GitHubClient:
    """Minimal GitHub Issues API client."""

    def __init__(self, token, repo=REPO):
        self.token = token
        self.repo = repo

    def _request(self, method, path, payload=None):
        url = f"https://api.github.com/repos/{self.repo}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "OpenProjectDirectory-Bot/1.0")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            if method == "DELETE" and exc.code == 404:
                return {}
            raise

    def get_issue(self, number):
        return self._request("GET", f"/issues/{number}")

    def list_issues(self, state="open", labels="submitted"):
        """List issues (used by the sweep to find stuck submissions)."""
        return self._request(
            "GET", f"/issues?state={state}&labels={labels}&per_page=100")

    def comment_issue(self, number, body):
        return self._request("POST", f"/issues/{number}/comments",
                             {"body": body})

    def add_labels(self, number, labels):
        if not labels:
            return {}
        return self._request("POST", f"/issues/{number}/labels",
                             {"labels": list(labels)})

    def remove_label(self, number, label):
        return self._request("DELETE", f"/issues/{number}/labels/{label}")

    def close_issue(self, number):
        return self._request("PATCH", f"/issues/{number}",
                             {"state": "closed"})


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _issue_labels(issue):
    return [label.get("name") for label in (issue or {}).get("labels") or []
            if isinstance(label, dict)]


def _is_submission_issue(issue):
    labels = _issue_labels(issue)
    title = (issue or {}).get("title") or ""
    if "submitted" in labels:
        return True
    if title.startswith("[Submission]"):
        return True
    # An issue with no labels at all (e.g. created via the API without the
    # template label) is treated as a submission; a labelled non-submission
    # (e.g. a report) is not.
    return not labels


def parse_and_normalize(issue_body):
    """Parse an issue body into a normalised submission dict."""
    data = parse_issue_body(issue_body or "")
    data["category"] = parse_categories(data.get("category", ""))
    data["additional_links"] = parse_links(data.get("additional_links", ""))
    if data.get("expedited_review"):
        data["expedited_review"] = parse_expedited_tier(data["expedited_review"])
    return normalize_submission(data)


def run_pipeline(issue_number, issue_body, data_path, client,
                 inspect_fn=None, today=None):
    """Run the full lifecycle for one issue. Returns an outcome dict.

    ``client`` needs get_issue / comment_issue / add_labels /
    remove_label / close_issue (GitHubClient, or a fake in tests).
    ``inspect_fn`` defaults to the real run_inspection; tests inject a
    fake returning (http, browser, doc, score) dicts.
    """
    inspect_fn = inspect_fn or run_inspection
    today = today or datetime.date.today().isoformat()
    issue = {}
    if hasattr(client, "get_issue"):
        try:
            issue = client.get_issue(issue_number) or {}
        except Exception:
            issue = {}
    if (issue.get("state") == "closed"
            and set(_issue_labels(issue)) & {"published", "failed"}):
        return {"outcome": "already_resolved", "issue_number": issue_number}
    if issue and not _is_submission_issue(issue):
        return {"outcome": "not_a_submission", "issue_number": issue_number}

    submission = parse_and_normalize(issue_body)
    valid, errors = validate_submission(submission)
    if not valid:
        client.comment_issue(issue_number, build_invalid_comment(errors))
        client.add_labels(issue_number, ["failed"])
        client.remove_label(issue_number, "queued")
        client.close_issue(issue_number)
        return {"outcome": "invalid", "issue_number": issue_number,
                "errors": errors}

    # Accepted: comment the fields received, then inspect.
    # Pricing default is decided when the project is built; for the
    # acceptance comment, note it only if the submitter left it blank.
    pricing_defaulted = not (submission.get("pricing") or "").strip()
    client.comment_issue(
        issue_number,
        build_acceptance_comment(submission, pricing_defaulted))
    client.add_labels(issue_number, ["queued"])
    client.add_labels(issue_number, ["inspecting"])
    client.comment_issue(issue_number, build_pending_comment(submission))

    http_result, browser_result, doc_result, score_result = inspect_fn(submission)
    client.comment_issue(
        issue_number,
        build_inspection_comment(submission, http_result, browser_result,
                                 doc_result, score_result))
    client.remove_label(issue_number, "inspecting")
    decision = score_result["decision"]

    # Duplicate: already listed — re-verified above, never added twice.
    catalog = load_catalog(data_path)
    duplicate = find_duplicate(submission, catalog.get("projects", []))
    if duplicate:
        client.comment_issue(
            issue_number, build_duplicate_comment(duplicate, score_result))
        client.add_labels(issue_number, ["published"])
        client.remove_label(issue_number, "queued")
        client.close_issue(issue_number)
        return {"outcome": "duplicate", "issue_number": issue_number,
                "slug": duplicate.get("slug"),
                "profile_url": profile_url(duplicate.get("slug", "")),
                "score": score_result["score"], "decision": decision}

    if decision == "auto_approve":
        project, _ = submission_to_project(
            submission, score_result, today=today,
            https_verified=bool((http_result or {}).get("https_ok")))
        added, _ = add_project_to_catalog(data_path, project)
        if not added:  # raced with another run; treat as duplicate
            client.comment_issue(
                issue_number, build_duplicate_comment(project, score_result))
            client.add_labels(issue_number, ["published"])
            client.remove_label(issue_number, "queued")
            client.close_issue(issue_number)
            return {"outcome": "duplicate", "issue_number": issue_number,
                    "slug": project["slug"],
                    "profile_url": profile_url(project["slug"]),
                    "score": score_result["score"], "decision": decision}
        client.add_labels(issue_number, ["passed"])
        client.remove_label(issue_number, "queued")
        return {"outcome": "publish", "issue_number": issue_number,
                "slug": project["slug"],
                "name": project["name"],
                "profile_url": profile_url(project["slug"]),
                "score": score_result["score"], "decision": decision}

    if decision == "manual_review":
        client.comment_issue(
            issue_number,
            build_manual_review_comment(submission, score_result))
        client.add_labels(issue_number, ["needs-review"])
        client.remove_label(issue_number, "queued")
        return {"outcome": "manual_review", "issue_number": issue_number,
                "score": score_result["score"], "decision": decision}

    # request_corrections / reject / hard fail -> denied.
    reasons = []
    if score_result.get("hard_fails"):
        reasons += [f"Hard fail: `{flag}` — blocks publication "
                    f"regardless of score."
                    for flag in score_result["hard_fails"]]
    reasons.append(
        f"Quality score {score_result['score']:.2f}/100 is in the "
        f"{band_text(decision)} band, below the 85-point bar for "
        "automatic approval.")
    if not (http_result or {}).get("dns_ok"):
        reasons.append("The website's DNS did not resolve.")
    if (http_result or {}).get("http_status") not in (200, None):
        reasons.append(
            f"The website returned HTTP {http_result.get('http_status')} "
            "instead of 200.")
    if not (browser_result or {}).get("rendered"):
        reasons.append("The website did not render usable content in a "
                       "headless browser (empty or placeholder page).")
    corrections = []
    if score_result["components"].get("documentation", 0) < 1.0:
        corrections.append("Add or expand public documentation (README / "
                           "docs page) — at least 200 words of real docs.")
    if score_result["components"].get("security_https", 0) < 1.0:
        corrections.append("Serve the site over valid HTTPS.")
    if score_result["components"].get("content_quality", 0) < 1.0:
        corrections.append("Make sure the site renders real content — no "
                           "empty, placeholder or “coming soon” page.")
    if score_result["components"].get("metadata_completeness", 0) < 1.0:
        corrections.append("Fill in the optional submission fields "
                           "(documentation, repository, pricing).")
    client.comment_issue(
        issue_number,
        build_denied_comment(submission, score_result, reasons, corrections))
    client.add_labels(issue_number, ["failed"])
    client.remove_label(issue_number, "queued")
    client.close_issue(issue_number)
    return {"outcome": "denied", "issue_number": issue_number,
            "score": score_result["score"], "decision": decision,
            "reasons": reasons}


def finalize_published(issue_number, outcome_path, client):
    """After the site is deployed: post the live URL, label, close."""
    with open(outcome_path, encoding="utf-8") as fh:
        outcome = json.load(fh)
    if outcome.get("outcome") != "publish":
        raise ValueError(
            f"finalize needs a publish outcome, got {outcome.get('outcome')!r}")
    project = {"name": outcome["name"], "slug": outcome["slug"]}
    score_result = {"score": outcome.get("score", 0),
                    "decision": outcome.get("decision", "auto_approve")}
    client.comment_issue(
        issue_number, build_published_comment(project, score_result))
    client.add_labels(issue_number, ["published"])
    client.remove_label(issue_number, "queued")
    client.remove_label(issue_number, "inspecting")
    client.close_issue(issue_number)
    return {"outcome": "published", "issue_number": issue_number,
            "slug": outcome["slug"],
            "profile_url": outcome.get("profile_url")}


def _write_outcome(outcome, outcome_path):
    with open(outcome_path, "w", encoding="utf-8") as fh:
        json.dump(outcome, fh, indent=2)
    # Expose the outcome to later workflow steps via GITHUB_OUTPUT.
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as fh:
            fh.write(f"outcome={outcome.get('outcome', '')}\n")
            if outcome.get("slug"):
                fh.write(f"slug={outcome['slug']}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Process one submission issue end to end.")
    parser.add_argument("--issue-number", required=True, type=int)
    parser.add_argument("--phase", choices=["process", "finalize"],
                        default="process")
    parser.add_argument("--issue-body", default=None,
                        help="Issue body text (or set ISSUE_BODY).")
    parser.add_argument("--data-path", default="data/projects.json")
    parser.add_argument("--outcome-path", default="pipeline_outcome.json")
    parser.add_argument("--repo", default=os.environ.get(
        "GITHUB_REPOSITORY", REPO))
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN", "")
    client = GitHubClient(token, repo=args.repo)
    if args.phase == "finalize":
        result = finalize_published(args.issue_number, args.outcome_path,
                                    client)
        print(json.dumps(result, indent=2))
        return 0

    issue_body = args.issue_body
    if issue_body is None:
        issue_body = os.environ.get("ISSUE_BODY", "")
    result = run_pipeline(args.issue_number, issue_body, args.data_path,
                          client)
    _write_outcome(result, args.outcome_path)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
