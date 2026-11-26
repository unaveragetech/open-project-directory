"""Validate a parsed submission. Returns (is_valid, [error strings])."""
import re
from urllib.parse import urlparse

REQUIRED = ["name", "website", "description", "category", "creator"]

EXPEDITED_TIERS = ("free", "standard", "priority", "same-day")
# Paid tiers — a transaction code is required so the donation can be
# verified against Cash App before the submission joins that queue.
PAID_EXPEDITED_TIERS = ("standard", "priority", "same-day")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_http_url(value):
    try:
        parsed = urlparse(value or "")
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def validate_submission(data):
    errors = []
    if not isinstance(data, dict):
        return False, ["submission is not a mapping"]
    for field in REQUIRED:
        value = data.get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            errors.append(f"missing required field: {field}")
    if data.get("website") and not _is_http_url(data["website"]):
        errors.append("website must be a valid http(s) URL")
    for field in ("documentation", "repository"):
        if data.get(field) and not _is_http_url(data[field]):
            errors.append(f"{field} must be a valid http(s) URL")
    if data.get("website", "").startswith("http://"):
        errors.append("website should use https where possible")
    categories = data.get("category") or []
    if isinstance(categories, str):
        categories = [categories]
    if not categories:
        errors.append("at least one category is required")
    tags = data.get("tags")
    if tags is not None and not isinstance(tags, (str, list)):
        errors.append("tags must be a comma-separated string or a list")
    elif isinstance(tags, list) and any(not isinstance(x, str) for x in tags):
        errors.append("each tag must be a string")
    pricing = (data.get("pricing") or "").strip().lower()
    if pricing and pricing not in ("free", "freemium", "paid", "open-source-free"):
        errors.append(f"unknown pricing value: {pricing}")
    # Expedited review: tier must be known; paid tiers need a transaction
    # code; a supplied contact email must look like an email. Free needs
    # no transaction code. A donation never guarantees approval — that is
    # a display/policy rule, not a validation rule.
    tier = (data.get("expedited_review") or "").strip().lower()
    if tier:
        # Accept the full form label too, e.g. "Standard — $5 donation …".
        tier_key = tier.split("—")[0].split("-")[0].strip()
        # "same-day" keeps its hyphen; handle it before the split above.
        if tier.startswith("same-day") or tier.startswith("same day"):
            tier_key = "same-day"
        if tier_key not in EXPEDITED_TIERS:
            errors.append(f"unknown expedited review tier: {tier}")
        elif tier_key in PAID_EXPEDITED_TIERS and not (data.get("transaction_code") or "").strip():
            errors.append(
                f"transaction code is required for the {tier_key} expedited tier "
                "(donate via Cash App, then email the code)")
    for email_field in ("contact_email",):
        if data.get(email_field) and not EMAIL_RE.match(str(data[email_field]).strip()):
            errors.append(f"{email_field} must be a valid email address")
    return (not errors), errors
