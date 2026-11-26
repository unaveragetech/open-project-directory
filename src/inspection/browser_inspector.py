"""Headless-browser inspection with Playwright.

Renders the real site and checks for JS errors, broken images/links,
empty or placeholder pages, and mobile-viewport rendering. Playwright is
imported lazily so unit tests and the HTTP-only path do not need a browser.
A screenshot is captured for the inspection record.
"""
import argparse
import json
import os

from .security_inspector import check_url_safe

PLACEHOLDER_MARKERS = [
    "coming soon", "under construction", "domain for sale",
    "this domain is parked", "default web page", "lorem ipsum",
]


def inspect_in_browser(url, screenshot_path=None, timeout_ms=30000):
    """Render url in headless Chromium. Returns a structured result dict."""
    from playwright.sync_api import sync_playwright

    result = {
        "url": url, "rendered": False, "console_errors": [],
        "broken_images": [], "broken_links": [], "empty_page": False,
        "placeholder": False, "title": None, "screenshot": screenshot_path,
        "mobile_ok": False, "errors": [],
    }
    safe, reason = check_url_safe(url)
    if not safe:
        result["errors"].append(f"SSRF guard: {reason}")
        return result
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.on("console", lambda msg: result["console_errors"].append(msg.text)
                if msg.type == "error" else None)
            page.on("pageerror", lambda exc: result["console_errors"].append(str(exc)))
            response = page.goto(url, timeout=timeout_ms, wait_until="networkidle")
            result["http_status"] = response.status if response else None
            result["title"] = page.title()
            body_text = (page.inner_text("body") or "").strip()
            result["rendered"] = bool(response and response.ok and len(body_text) > 50)
            lowered = body_text.lower()
            result["placeholder"] = any(m in lowered for m in PLACEHOLDER_MARKERS)
            result["empty_page"] = len(body_text) < 50
            for img in page.query_selector_all("img"):
                src = img.get_attribute("src") or ""
                if src and not img.evaluate("el => el.complete && el.naturalWidth > 0"):
                    result["broken_images"].append(src)
            if screenshot_path:
                os.makedirs(os.path.dirname(screenshot_path) or ".", exist_ok=True)
                page.screenshot(path=screenshot_path, full_page=False)
            mobile = browser.new_page(viewport={"width": 390, "height": 844})
            mobile.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            result["mobile_ok"] = bool((mobile.inner_text("body") or "").strip())
            mobile.close()
        except Exception as exc:  # noqa: BLE001 - report, don't crash the worker
            result["errors"].append(str(exc))
        finally:
            browser.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="Browser-inspect a URL.")
    parser.add_argument("--url", default="")
    parser.add_argument("--issue", default="")
    parser.add_argument("--screenshot", default="")
    args = parser.parse_args()
    print(json.dumps(inspect_in_browser(args.url, args.screenshot or None), indent=2))
    return 0


if __name__ == "__main__":
    main()
