"""Sweep stuck submissions: drain every open issue that the pipeline
never finished, in a single run.

Why this exists (2026-11-26): when 8 issues were submitted within 30
seconds, 6 of their pipeline runs were cancelled before they posted a
single comment — GitHub drops all but the newest *waiting* run in a
shared concurrency group, even with cancel-in-progress: false — and one
more scored 100/100 but failed to publish on a stale push. A single
issue-triggered run cannot be relied on to finish a batch.

The sweep (`.github/workflows/sweep.yml`, every 15 minutes) finds every
open issue that still carries only the `submitted` label and has had no
activity for 10+ minutes, runs the full pipeline for each one — oldest
first, capped per sweep — commits all catalog additions in one commit,
and leaves deploy + finalize to the workflow steps, exactly like the
per-issue workflow. An issue a run is currently setting up, or one just
edited, is skipped by the 10-minute quiet rule, so the sweep never
fights a live run.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from .process_issue import GitHubClient, REPO, run_pipeline

STUCK_LABELS = {"submitted"}
# An issue counts as stuck only after this long with no activity, so a
# run that is still installing Playwright, or an issue just edited to
# re-trigger its run, is never grabbed mid-flight.
STUCK_QUIET = timedelta(minutes=10)
MAX_ISSUES_PER_SWEEP = 5


def _parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_stuck(issue, now=None):
    """An open issue the pipeline never touched: only the `submitted`
    label, and no update for at least STUCK_QUIET."""
    now = now or datetime.now(timezone.utc)
    if issue.get("state") != "open":
        return False
    labels = {label.get("name") for label in issue.get("labels", [])}
    if labels != STUCK_LABELS:
        return False
    updated = _parse_time(issue.get("updated_at"))
    if updated is None or now - updated < STUCK_QUIET:
        return False
    return True


def find_stuck_issues(client, now=None):
    """All stuck submission issues, oldest first."""
    issues = client.list_issues(state="open", labels="submitted")
    stuck = [issue for issue in issues if is_stuck(issue, now=now)]
    stuck.sort(key=lambda issue: issue.get("created_at") or "")
    return stuck


def _git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


def commit_catalog(data_path, count, cwd=None):
    """Commit every catalog addition from this sweep in one commit,
    rebased onto the latest main first (see submission.yml: commit
    first, then rebase, then push — pulling before the commit fails on
    the uncommitted change)."""
    _git("config", "user.name", "github-actions[bot]", cwd=cwd)
    _git("config", "user.email",
         "41898282+github-actions[bot]@users.noreply.github.com", cwd=cwd)
    _git("add", data_path, cwd=cwd)
    _git("commit", "-m",
         f"Add {count} project(s) from submission sweep", cwd=cwd)
    _git("pull", "--rebase", "origin", "main", cwd=cwd)
    _git("push", cwd=cwd)


def sweep(data_path, client, out_dir=".", inspect_fn=None, now=None,
          max_issues=MAX_ISSUES_PER_SWEEP, commit=True):
    """Process every stuck issue. Returns a summary dict with the
    publish outcomes and the issue numbers that were published."""
    now = now or datetime.now(timezone.utc)
    stuck = find_stuck_issues(client, now=now)[:max_issues]
    results, published = [], []
    for issue in stuck:
        number = issue["number"]
        result = run_pipeline(number, issue.get("body") or "", data_path,
                              client, inspect_fn=inspect_fn)
        results.append(result)
        if result.get("outcome") == "publish":
            published.append(number)
            with open(os.path.join(out_dir, f"pipeline_outcome_{number}.json"),
                      "w", encoding="utf-8") as fh:
                json.dump(result, fh, indent=2)
    if published and commit:
        commit_catalog(data_path, len(published))
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as fh:
            fh.write(f"published={','.join(str(n) for n in published)}\n")
            fh.write(f"published_any={'true' if published else 'false'}\n")
    return {"stuck_found": len(stuck), "published": published,
            "results": results}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Drain stuck submission issues in one run.")
    parser.add_argument("--data-path", default="data/projects.json")
    parser.add_argument("--out-dir", default=".")
    parser.add_argument("--max-issues", type=int,
                        default=MAX_ISSUES_PER_SWEEP)
    parser.add_argument("--no-commit", action="store_true",
                        help="Do not commit/push the catalog change.")
    parser.add_argument("--repo", default=os.environ.get(
        "GITHUB_REPOSITORY", REPO))
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 1
    client = GitHubClient(token, repo=args.repo)
    summary = sweep(args.data_path, client, out_dir=args.out_dir,
                    max_issues=args.max_issues, commit=not args.no_commit)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
