"""Parse a GitHub issue body (submit-project.yml form) into a submission dict.

The issue template renders as Markdown headings followed by values, e.g.:

    ### Project name
    Example AI Assistant

    ### Website URL
    https://example.com

Fields are matched case-insensitively by heading text. Untrusted input is
treated as data only — nothing here is executed.
"""
import argparse
import json
import re
import sys

FIELD_MAP = {
    "project name": "name",
    "website url": "website",
    "description": "description",
    "category": "category",
    "documentation url": "documentation",
    "repository url": "repository",
    "creator": "creator",
    "contact": "contact",
    "pricing": "pricing",
    "additional details": "flags",
    "additional links": "additional_links",
    "expedited review": "expedited_review",
    "transaction code": "transaction_code",
    "expedited email": "contact_email",
    "contact email": "contact_email",
}

HEADING_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)


def parse_issue_body(body):
    """Parse issue body Markdown into a dict of submission fields."""
    if not body:
        return {}
    sections = {}
    matches = list(HEADING_RE.finditer(body))
    for i, match in enumerate(matches):
        heading = match.group(1).strip().lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        value = body[start:end].strip()
        # GitHub form "no response" placeholder means empty.
        if value.lower() in ("_no response_", "no response"):
            value = ""
        key = FIELD_MAP.get(heading)
        if key:
            sections[key] = value
    return sections


def parse_categories(raw):
    if not raw:
        return []
    return [c.strip() for c in re.split(r"[,\\n]", raw) if c.strip()]


def parse_links(raw):
    if not raw:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


# Expedited-review tier labels from the issue form -> canonical keys.
# Form values look like "Standard — $5 donation (3–5 days)".
EXPEDITED_TIER_LABELS = {
    "free": "free",
    "standard": "standard",
    "priority": "priority",
    "same-day": "same-day",
    "same day": "same-day",
}


def parse_expedited_tier(raw):
    """Map a form label / free text to a tier key, or '' if none given."""
    if not raw:
        return ""
    text = str(raw).strip().lower()
    for label, key in EXPEDITED_TIER_LABELS.items():
        if text.startswith(label):
            return key
    return text


def main():
    parser = argparse.ArgumentParser(description="Parse a submission issue body.")
    parser.add_argument("--issue-body", default="")
    parser.add_argument("--issue-number", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = parse_issue_body(args.issue_body)
    data["category"] = parse_categories(data.get("category", ""))
    data["additional_links"] = parse_links(data.get("additional_links", ""))
    if data.get("expedited_review"):
        data["expedited_review"] = parse_expedited_tier(data["expedited_review"])
    if args.issue_number:
        data["github_issue_id"] = args.issue_number
    if args.json or True:
        print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
