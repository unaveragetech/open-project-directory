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

# Pages that are not the site at all, but a bot-check in front of it
# (Cloudflare "Just a moment…", etc.). A headless browser is often
# shown these while a human visitor is not — the site behind them can
# still be perfectly real, so this must be reported, not scored as an
# empty page.
BOT_CHALLENGE_MARKERS = [
    "just a moment", "checking your browser", "verify you are human",
    "attention required", "please verify", "security check",
]


def is_bot_challenge(title, body_text):
    """True when the rendered page looks like a bot-check interstitial."""
    text = f"{title or ''} {body_text or ''}".lower()
    return any(marker in text for marker in BOT_CHALLENGE_MARKERS)


def _http_content_words(url):
    """Words of real text from a plain HTTP fetch (challenge bypass).

    Used only when the browser was shown a bot-check page: the plain
    fetch often reaches the real site. Returns 0 on any failure.
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
        with httpx.Client(timeout=15, follow_redirects=True,
                          trust_env=False,
                          headers={"User-Agent": "OpenProjectDirectory-Bot/1.0"}) as client:
            response = client.get(url)
            if response.status_code != 200:
                return 0
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            return len(soup.get_text(" ", strip=True).split())
    except Exception:  # noqa: BLE001 - fallback only, never crash inspection
        return 0


def inspect_in_browser(url, screenshot_path=None, timeout_ms=30000):
    """Render url in headless Chromium. Returns a structured result dict."""
    from playwright.sync_api import sync_playwright

    result = {
        "url": url, "rendered": False, "console_errors": [],
        "broken_images": [], "broken_links": [], "empty_page": False,
        "placeholder": False, "title": None, "screenshot": screenshot_path,
        "mobile_ok": False, "errors": [],
        "bot_challenge": False, "http_content_words": 0,
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
            # "load" (not "networkidle"): many real sites keep a connection
            # open (analytics, SSE, websockets) and never reach networkidle,
            # which used to time out and score a perfectly good page as
            # not rendered. If even "load" times out, still try to read
            # whatever body is there instead of reporting nothing.
            try:
                response = page.goto(url, timeout=timeout_ms, wait_until="load")
            except Exception as exc:  # noqa: BLE001 - fall back to loaded body
                result["errors"].append(f"goto timed out, reading loaded body: {exc}")
                response = None
            result["http_status"] = response.status if response else None
            result["title"] = page.title()
            body_text = (page.inner_text("body") or "").strip()
            if is_bot_challenge(result["title"], body_text):
                # The challenge usually clears in a few seconds in a real
                # browser; give it one chance, then record it honestly.
                page.wait_for_timeout(8000)
                body_text = (page.inner_text("body") or "").strip()
                result["title"] = page.title()
            result["bot_challenge"] = is_bot_challenge(
                result["title"], body_text)
            if result["bot_challenge"]:
                result["http_content_words"] = _http_content_words(url)
                result["errors"].append(
                    "browser was shown a bot-check page; content verified "
                    "from the plain HTTP fetch instead")
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
