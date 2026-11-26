"""Tests for the end-to-end submission pipeline (src/pipeline)."""
import json
import os
import shutil

import pytest
import yaml

from src.inspection.scoring import score_inspection
from src.pipeline.process_issue import (
    OUTCOME_MAP,
    build_acceptance_comment,
    build_denied_comment,
    build_duplicate_comment,
    build_inspection_comment,
    build_invalid_comment,
    build_published_comment,
    finalize_published,
    profile_url,
    run_pipeline,
    submission_to_project,
)

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")


class FakeClient:
    """Stand-in for GitHubClient: records comments/labels/close calls."""

    def __init__(self, labels=None, state="open",
                 title="[Submission] Test Project"):
        self.labels = list(labels if labels is not None else ["submitted"])
        self.state = state
        self.title = title
        self.comments = []
        self.closed = False

    def get_issue(self, number):
        return {"number": number, "state": self.state, "title": self.title,
                "labels": [{"name": label} for label in self.labels]}

    def comment_issue(self, number, body):
        self.comments.append(body)
        return {}

    def add_labels(self, number, labels):
        for label in labels:
            if label not in self.labels:
                self.labels.append(label)
        return {}

    def remove_label(self, number, label):
        self.labels = [item for item in self.labels if item != label]
        return {}

    def close_issue(self, number):
        self.state = "closed"
        self.closed = True
        return {}


BODY = """### Project name
Test Project

### Website URL
https://example.com

### Description
Does useful things for developers.

### Category
AI, Developer Tools

### Documentation URL
https://docs.example.com

### Repository URL
https://github.com/example/project

### Creator
Jesse

### Pricing
free
"""

TOKENBROKER_BODY = """### Project name
TokenBroker

### Website URL
https://tokenbroker.org

### Description
Prepaid OpenAI-compatible AI API gateway.

### Category
AI, Developer Tools

### Documentation URL
https://tokenbroker.org/docs

### Creator
Jesse

### Pricing
freemium
"""


def _http_ok():
    return {"http_status": 200, "dns_ok": True, "https_ok": True,
            "final_url": "https://example.com", "tls_version": "TLSv1.3",
            "missing_security_headers": [], "robots_txt": True,
            "sitemap": True, "errors": []}


def _browser_ok():
    return {"rendered": True, "empty_page": False, "placeholder": False,
            "title": "Example", "console_errors": [], "broken_images": [],
            "broken_links": [], "mobile_ok": True, "errors": []}


def _docs_ok():
    return {"documentation": {"word_count": 500,
                              "source_url": "https://docs.example.com"},
            "errors": []}


def _fake_inspect(decision_target="perfect"):
    """Return an inspect_fn producing a chosen decision band."""

    def inspect(submission):
        if decision_target == "perfect":
            http, browser, docs = _http_ok(), _browser_ok(), _docs_ok()
        elif decision_target == "manual_review":
            # Docs missing -> 77.5, manual review.
            http, browser, docs = _http_ok(), _browser_ok(), \
                {"documentation": None, "errors": []}
            browser = dict(browser, console_errors=["boom"])
        elif decision_target == "corrections":
            # Site up but renders nothing, no docs -> 50.0, request corrections.
            http, browser, docs = _http_ok(), \
                {"rendered": False, "empty_page": True, "placeholder": False,
                 "title": None, "console_errors": [], "broken_images": [],
                 "broken_links": [], "mobile_ok": False, "errors": []}, \
                {"documentation": None, "errors": []}
        elif decision_target == "bad":
            http = {"http_status": None, "dns_ok": False, "https_ok": False,
                    "final_url": None, "missing_security_headers": [],
                    "errors": ["DNS failed"]}
            browser = {"rendered": False, "empty_page": True,
                       "placeholder": False, "title": None,
                       "console_errors": [], "broken_images": [],
                       "broken_links": [], "mobile_ok": False, "errors": []}
            docs = {"documentation": None, "errors": []}
        elif decision_target == "hard_fail":
            http, browser, docs = _http_ok(), _browser_ok(), _docs_ok()
            submission = dict(submission,
                              hard_fail_flags=["malware_detected"])
        else:  # pragma: no cover
            raise ValueError(decision_target)
        score = score_inspection(http, browser, docs, submission)
        return http, browser, docs, score

    return inspect


def _catalog(tmp_path, projects):
    path = tmp_path / "projects.json"
    path.write_text(json.dumps({"projects": projects}), encoding="utf-8")
    return str(path)


def _tokenbroker_entry():
    return {"name": "TokenBroker", "slug": "tokenbroker",
            "website_url": "https://tokenbroker.org",
            "creator": "Jesse", "category": ["AI"],
            "description": "Prepaid API gateway.", "pricing": "freemium",
            "tags": ["ai"]}


# --- comment builders -------------------------------------------------------

def test_acceptance_comment_lists_fields_and_next_steps():
    from src.pipeline.process_issue import parse_and_normalize
    submission = parse_and_normalize(BODY)
    comment = build_acceptance_comment(submission)
    assert "Test Project" in comment
    assert "https://example.com" in comment
    assert "queued" in comment.lower()
    assert "Inspection" in comment and "Publish or deny" in comment


def test_invalid_comment_names_each_missing_field():
    comment = build_invalid_comment(
        ["missing required field: creator", "website must be a valid http(s) URL"])
    assert "missing required field: creator" in comment
    assert "website must be a valid http(s) URL" in comment
    assert "`failed`" in comment


def test_inspection_comment_has_score_table_band_and_findings():
    submission = {"name": "Test Project", "website": "https://example.com"}
    score = score_inspection(_http_ok(), _browser_ok(), _docs_ok(),
                             {"name": "x", "website": "https://example.com",
                              "description": "d", "category": ["AI"],
                              "creator": "c",
                              "documentation": "https://docs.example.com",
                              "repository": "https://github.com/e/p",
                              "pricing": "free"})
    comment = build_inspection_comment(submission, _http_ok(), _browser_ok(),
                                       _docs_ok(), score)
    assert "100" in comment
    assert "85–100" in comment
    assert "Website Accessibility" in comment
    assert "TLSv1.3" in comment
    assert "robots.txt" in comment


def test_denied_comment_has_reasons_and_corrections():
    comment = build_denied_comment(
        {"name": "Bad Project"},
        {"score": 30.0, "decision": "reject", "hard_fails": []},
        ["Quality score 30.00/100 is too low."],
        ["Serve the site over valid HTTPS."])
    assert "Bad Project" in comment
    assert "30.00/100" in comment
    assert "Serve the site over valid HTTPS." in comment
    assert "`failed`" in comment


def test_duplicate_comment_has_live_url():
    comment = build_duplicate_comment(_tokenbroker_entry())
    assert profile_url("tokenbroker") in comment
    assert "Already listed" in comment
    assert "`published`" in comment


def test_published_comment_has_profile_url():
    comment = build_published_comment(
        {"name": "Test Project", "slug": "test-project"},
        {"score": 92.0, "decision": "auto_approve"})
    assert profile_url("test-project") in comment
    assert "92.00/100" in comment


def test_outcome_map_covers_all_decisions():
    assert OUTCOME_MAP["publish"] == ("published", True, True)
    assert OUTCOME_MAP["manual_review"] == ("needs-review", False, False)
    assert OUTCOME_MAP["denied"] == ("failed", True, False)
    assert OUTCOME_MAP["invalid"] == ("failed", True, False)
    assert OUTCOME_MAP["duplicate"] == ("published", True, False)


def test_submission_to_project_invents_no_features():
    from src.pipeline.process_issue import parse_and_normalize
    submission = parse_and_normalize(BODY)
    project, _ = submission_to_project(
        submission, {"score": 95.0}, today="2026-11-25", https_verified=True)
    assert project["slug"] == "test-project"
    assert project["features"] == []
    assert project["tags"] == ["ai", "developer-tools"]
    assert project["quality_score"] == 95
    assert project["last_verified"] == "2026-11-25"
    assert project["https_verified"] is True


# --- full pipeline runs with a fake client ----------------------------------

def test_invalid_submission_closes_with_failed_label(tmp_path):
    client = FakeClient()
    data_path = _catalog(tmp_path, [])
    outcome = run_pipeline(1, "### Project name\nNope\n", data_path, client)
    assert outcome["outcome"] == "invalid"
    assert "missing required field" in " ".join(outcome["errors"])
    assert client.closed
    assert "failed" in client.labels
    assert any("needs fixes" in c for c in client.comments)
    assert json.loads(open(data_path).read())["projects"] == []


def test_publish_path_adds_project_and_waits_for_finalize(tmp_path):
    client = FakeClient()
    data_path = _catalog(tmp_path, [])
    outcome = run_pipeline(2, BODY, data_path, client,
                           inspect_fn=_fake_inspect("perfect"),
                           today="2026-11-25")
    assert outcome["outcome"] == "publish"
    assert outcome["slug"] == "test-project"
    assert outcome["profile_url"] == profile_url("test-project")
    projects = json.loads(open(data_path).read())["projects"]
    assert len(projects) == 1
    assert projects[0]["name"] == "Test Project"
    assert projects[0]["features"] == []  # nothing invented
    # Not closed yet: the workflow deploys first, finalize closes it.
    assert not client.closed
    assert "passed" in client.labels
    assert "queued" not in client.labels
    assert any("Submission accepted" in c for c in client.comments)
    assert any("Inspection running" in c for c in client.comments)
    assert any("Inspection results" in c for c in client.comments)


def test_finalize_posts_live_url_labels_published_and_closes(tmp_path):
    client = FakeClient(labels=["submitted", "passed"])
    outcome_path = tmp_path / "pipeline_outcome.json"
    outcome_path.write_text(json.dumps({
        "outcome": "publish", "issue_number": 2, "slug": "test-project",
        "name": "Test Project", "profile_url": profile_url("test-project"),
        "score": 100.0, "decision": "auto_approve"}), encoding="utf-8")
    result = finalize_published(2, str(outcome_path), client)
    assert result["outcome"] == "published"
    assert result["profile_url"] == profile_url("test-project")
    assert client.closed
    assert "published" in client.labels
    assert any("Published!" in c and profile_url("test-project") in c
               for c in client.comments)


def test_duplicate_runs_inspection_then_closes_as_published(tmp_path):
    client = FakeClient(title="[Submission] TokenBroker")
    data_path = _catalog(tmp_path, [_tokenbroker_entry()])
    outcome = run_pipeline(3, TOKENBROKER_BODY, data_path, client,
                           inspect_fn=_fake_inspect("perfect"),
                           today="2026-11-25")
    assert outcome["outcome"] == "duplicate"
    assert outcome["slug"] == "tokenbroker"
    projects = json.loads(open(data_path).read())["projects"]
    assert len(projects) == 1  # no duplicate added
    assert client.closed
    assert "published" in client.labels
    joined = "\n".join(client.comments)
    assert "Submission accepted" in joined
    assert "Inspection running" in joined
    assert "Inspection results" in joined
    assert "Already listed" in joined
    assert profile_url("tokenbroker") in joined


def test_manual_review_leaves_issue_open_with_needs_review(tmp_path):
    client = FakeClient()
    data_path = _catalog(tmp_path, [])
    outcome = run_pipeline(4, BODY, data_path, client,
                           inspect_fn=_fake_inspect("manual_review"),
                           today="2026-11-25")
    assert outcome["outcome"] == "manual_review"
    assert not client.closed
    assert "needs-review" in client.labels
    assert any("Manual review needed" in c for c in client.comments)
    assert json.loads(open(data_path).read())["projects"] == []


def test_denied_low_score_closes_with_failed_and_reasons(tmp_path):
    client = FakeClient()
    data_path = _catalog(tmp_path, [])
    outcome = run_pipeline(5, BODY, data_path, client,
                           inspect_fn=_fake_inspect("bad"),
                           today="2026-11-25")
    assert outcome["outcome"] == "denied"
    assert client.closed
    assert "failed" in client.labels
    joined = "\n".join(client.comments)
    assert "Submission denied" in joined
    assert "Why it failed" in joined
    assert json.loads(open(data_path).read())["projects"] == []


def test_request_corrections_band_is_denied_for_now(tmp_path):
    client = FakeClient()
    data_path = _catalog(tmp_path, [])
    outcome = run_pipeline(6, BODY, data_path, client,
                           inspect_fn=_fake_inspect("corrections"),
                           today="2026-11-25")
    assert outcome["outcome"] == "denied"
    assert outcome["decision"] == "request_corrections"
    assert client.closed
    assert "failed" in client.labels


def test_hard_fail_denied_even_with_high_score(tmp_path):
    client = FakeClient()
    data_path = _catalog(tmp_path, [])
    outcome = run_pipeline(7, BODY, data_path, client,
                           inspect_fn=_fake_inspect("hard_fail"),
                           today="2026-11-25")
    assert outcome["outcome"] == "denied"
    assert outcome["decision"] == "reject"
    assert any("malware_detected" in c for c in client.comments)
    assert client.closed


def test_already_resolved_issue_is_skipped(tmp_path):
    client = FakeClient(labels=["submitted", "published"], state="closed")
    data_path = _catalog(tmp_path, [])
    outcome = run_pipeline(8, BODY, data_path, client,
                           inspect_fn=_fake_inspect("perfect"))
    assert outcome["outcome"] == "already_resolved"
    assert client.comments == []


def test_non_submission_issue_is_skipped(tmp_path):
    client = FakeClient(labels=["bug"], title="Something is broken")
    data_path = _catalog(tmp_path, [])
    outcome = run_pipeline(9, BODY, data_path, client,
                           inspect_fn=_fake_inspect("perfect"))
    assert outcome["outcome"] == "not_a_submission"
    assert client.comments == []


# --- workflow wiring ---------------------------------------------------------

def test_submission_workflow_has_write_permissions_and_deploy():
    path = os.path.join(REPO_ROOT, ".github", "workflows", "submission.yml")
    with open(path, encoding="utf-8") as fh:
        workflow = yaml.safe_load(fh)
    permissions = workflow["permissions"]
    assert permissions["contents"] == "write"
    assert permissions["issues"] == "write"
    assert permissions["pages"] == "write"
    assert permissions["id-token"] == "write"
    text = open(path, encoding="utf-8").read()
    assert "process_issue" in text
    assert "--phase finalize" in text
    assert "deploy-pages" in text
    assert "published" in text
