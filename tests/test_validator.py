from src.submission.validator import validate_submission
from src.submission.normalizer import normalize_submission, slugify, find_duplicate


def _valid():
    return {"name": "Example", "website": "https://example.com",
            "description": "Does things.", "category": ["AI"],
            "creator": "Someone"}


def test_valid_submission_passes():
    ok, errors = validate_submission(_valid())
    assert ok and errors == []


def test_missing_required_field_fails():
    data = _valid()
    del data["website"]
    ok, errors = validate_submission(data)
    assert not ok and any("website" in e for e in errors)


def test_bad_url_fails():
    data = _valid()
    data["website"] = "not-a-url"
    ok, errors = validate_submission(data)
    assert not ok


def test_normalizer_slug_and_url():
    out = normalize_submission({"name": "Example AI Assistant",
                                "website": "https://Example.com/"})
    assert out["slug"] == "example-ai-assistant"
    assert out["website"] == "https://example.com"


def test_slugify():
    assert slugify("Dead Grid!") == "dead-grid"


def test_duplicate_detection_by_website():
    existing = [{"slug": "example", "website_url": "https://example.com"}]
    dup = find_duplicate({"website": "https://example.com", "slug": "other"}, existing)
    assert dup is not None
    assert find_duplicate({"website": "https://other.com", "slug": "other"}, existing) is None
