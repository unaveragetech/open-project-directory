from src.submission.parser import parse_issue_body, parse_categories


def test_parse_issue_body_extracts_fields():
    body = """### Project name
Example AI Assistant

### Website URL
https://example.com

### Description
An AI assistant for developers.

### Category
AI, Developer Tools

### Creator
Example Developer
"""
    data = parse_issue_body(body)
    assert data["name"] == "Example AI Assistant"
    assert data["website"] == "https://example.com"
    assert data["description"] == "An AI assistant for developers."
    assert data["creator"] == "Example Developer"


def test_parse_issue_body_ignores_no_response():
    body = "### Documentation URL\n_No response_\n\n### Project name\nTest\n"
    data = parse_issue_body(body)
    assert data.get("documentation") == ""
    assert data["name"] == "Test"


def test_parse_categories():
    assert parse_categories("AI, Developer Tools") == ["AI", "Developer Tools"]
    assert parse_categories("") == []
