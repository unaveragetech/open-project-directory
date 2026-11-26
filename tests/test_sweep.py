"""Sweep: drain stuck submissions that the per-issue pipeline never
finished (see src/pipeline/sweep.py)."""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from src.pipeline.sweep import find_stuck_issues, is_stuck, sweep
from tests.test_pipeline import BODY, FakeClient, _fake_inspect

NOW = datetime(2026, 11, 26, 1, 0, tzinfo=timezone.utc)


def _body(name, website):
    return BODY.replace("Test Project", name).replace(
        "https://example.com", website)


def _issue(number, labels=("submitted",), updated_hours_ago=1,
           state="open"):
    updated = (NOW - timedelta(hours=updated_hours_ago)).isoformat()
    created = (NOW - timedelta(hours=updated_hours_ago + 1)).isoformat()
    return {"number": number, "state": state, "title": "[Submission] X",
            "labels": [{"name": label} for label in labels],
            "updated_at": updated, "created_at": created,
            "body": _body(f"Test Project {number}",
                          f"https://example{number}.com")}


class ListClient(FakeClient):
    """FakeClient that can also list issues for the sweep."""

    def __init__(self, issues, **kwargs):
        super().__init__(**kwargs)
        self._issues = issues
        self.get_issue_map = {i["number"]: i for i in issues}

    def list_issues(self, state="open", labels="submitted"):
        return [i for i in self._issues if i["state"] == state]

    def get_issue(self, number):
        issue = self.get_issue_map.get(number)
        if issue is None:
            return super().get_issue(number)
        return {"number": number, "state": issue["state"],
                "title": issue["title"],
                "labels": [{"name": l} for l in
                           [x["name"] for x in issue["labels"]]]}


def test_is_stuck_only_submitted_and_quiet():
    assert is_stuck(_issue(1), now=NOW)
    assert not is_stuck(_issue(2, updated_hours_ago=0.05), now=NOW), \
        "just edited: a run may be setting up"
    assert not is_stuck(_issue(3, labels=("submitted", "queued")), now=NOW)
    assert not is_stuck(_issue(4, labels=("submitted", "passed")), now=NOW)
    assert not is_stuck(_issue(5, state="closed"), now=NOW)


def test_find_stuck_oldest_first():
    issues = [_issue(9, updated_hours_ago=2), _issue(4, updated_hours_ago=5),
              _issue(7, labels=("submitted", "queued"))]
    found = find_stuck_issues(ListClient(issues), now=NOW)
    assert [i["number"] for i in found] == [4, 9]


def test_sweep_publishes_all_stuck_in_one_pass(tmp_path):
    data_path = os.path.join(tmp_path, "projects.json")
    with open(data_path, "w", encoding="utf-8") as fh:
        json.dump({"projects": []}, fh)
    issues = [_issue(4, updated_hours_ago=5), _issue(5, updated_hours_ago=3)]
    client = ListClient(issues)
    summary = sweep(data_path, client, out_dir=str(tmp_path),
                    inspect_fn=_fake_inspect("perfect"), now=NOW,
                    commit=False)
    assert summary["stuck_found"] == 2
    assert summary["published"] == [4, 5]
    catalog = json.load(open(data_path, encoding="utf-8"))
    assert len(catalog["projects"]) == 2
    for number in (4, 5):
        outcome = json.load(open(
            os.path.join(tmp_path, f"pipeline_outcome_{number}.json"),
            encoding="utf-8"))
        assert outcome["outcome"] == "publish"
    assert "passed" in client.labels


def test_sweep_noop_when_nothing_stuck(tmp_path):
    data_path = os.path.join(tmp_path, "projects.json")
    with open(data_path, "w", encoding="utf-8") as fh:
        json.dump({"projects": []}, fh)
    issues = [_issue(4, labels=("submitted", "passed")),
              _issue(5, updated_hours_ago=0.05)]
    summary = sweep(data_path, ListClient(issues), out_dir=str(tmp_path),
                    inspect_fn=_fake_inspect("perfect"), now=NOW,
                    commit=False)
    assert summary == {"stuck_found": 0, "published": [], "results": []}
    assert json.load(open(data_path, encoding="utf-8"))["projects"] == []


def test_sweep_respects_max_issues(tmp_path):
    data_path = os.path.join(tmp_path, "projects.json")
    with open(data_path, "w", encoding="utf-8") as fh:
        json.dump({"projects": []}, fh)
    issues = [_issue(n, updated_hours_ago=n) for n in (4, 5, 6, 7, 8)]
    summary = sweep(data_path, ListClient(issues), out_dir=str(tmp_path),
                    inspect_fn=_fake_inspect("perfect"), now=NOW,
                    commit=False, max_issues=2)
    assert summary["stuck_found"] == 2
    assert len(summary["published"]) == 2


def test_sweep_workflow_parses_and_serializes():
    import yaml
    with open(os.path.join(os.path.dirname(__file__), "..",
                           ".github", "workflows", "sweep.yml"),
              encoding="utf-8") as fh:
        workflow = yaml.safe_load(fh)
    # PyYAML reads the `on:` key as boolean True (YAML 1.1).
    assert workflow[True]["schedule"] == [{"cron": "*/15 * * * *"}]
    assert workflow["concurrency"]["group"] == "submission-pipeline"
    assert workflow["concurrency"]["cancel-in-progress"] is False
    steps = workflow["jobs"]["sweep"]["steps"]
    assert any("src.pipeline.sweep" in str(s.get("run", "")) for s in steps)
    assert any("deploy-pages" in str(s.get("uses", "")) for s in steps)
