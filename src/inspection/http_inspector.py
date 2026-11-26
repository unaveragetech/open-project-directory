"""HTTP inspection: DNS, TLS, redirects, headers, robots/sitemap.

Real checks via httpx + ssl + dnspython. Every fetched URL passes through
the SSRF guard in security_inspector, including redirect targets.
"""
import argparse
import json
import socket
import ssl
from urllib.parse import urljoin, urlparse

import httpx

from .security_inspector import check_url_safe, revalidate_redirect_url, MAX_RESPONSE_BYTES

TIMEOUT = 15.0
USER_AGENT = "OpenProjectDirectory-Bot/1.0 (+https://unaveragetech.github.io/open-project-directory)"
SECURITY_HEADERS = [
    "content-security-policy",
    "strict-transport-security",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
]


def check_tls(host, port=443):
    """Return dict with TLS validity; never raises."""
    result = {"tls_available": False, "tls_valid": False, "error": None}
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert()
                result["tls_available"] = True
                result["tls_valid"] = bool(cert)
                result["tls_version"] = tls.version()
    except Exception as exc:  # noqa: BLE001 - report, don't crash the worker
        result["error"] = str(exc)
    return result


def inspect_url(url):
    """Inspect one URL. Returns a structured result dict."""
    result = {
        "url": url, "dns_ok": False, "https_ok": False, "http_status": None,
        "final_url": None, "redirect_chain": [], "content_type": None,
        "security_headers": {}, "missing_security_headers": [],
        "robots_txt": False, "sitemap": False, "canonical": None,
        "errors": [], "checks": {},
    }
    safe, reason = check_url_safe(url)
    if not safe:
        result["errors"].append(f"SSRF guard: {reason}")
        result["checks"]["ssrf"] = "FAIL"
        return result
    parsed = urlparse(url)
    host = parsed.hostname
    try:
        socket.getaddrinfo(host, None)
        result["dns_ok"] = True
        result["checks"]["dns"] = "PASS"
    except socket.gaierror as exc:
        result["errors"].append(f"DNS failed: {exc}")
        result["checks"]["dns"] = "FAIL"
        return result
    if parsed.scheme == "https":
        tls = check_tls(host)
        result.update({f"tls_{k}": v for k, v in tls.items()})
        result["https_ok"] = bool(tls["tls_valid"])
        result["checks"]["tls"] = "PASS" if result["https_ok"] else "FAIL"
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=False,
                          headers={"User-Agent": USER_AGENT}) as client:
            current = url
            for _ in range(6):
                response = client.get(current)
                result["redirect_chain"].append(
                    {"url": current, "status": response.status_code})
                if response.status_code in (301, 302, 303, 307, 308):
                    target = urljoin(current, response.headers.get("location", ""))
                    ok, why = revalidate_redirect_url(target)
                    if not ok:
                        result["errors"].append(f"unsafe redirect target: {why}")
                        result["checks"]["redirects"] = "FAIL"
                        break
                    current = target
                    continue
                result["http_status"] = response.status_code
                result["final_url"] = current
                result["content_type"] = response.headers.get("content-type")
                for header in SECURITY_HEADERS:
                    if header in response.headers:
                        result["security_headers"][header] = response.headers[header]
                    else:
                        result["missing_security_headers"].append(header)
                if len(response.content) > MAX_RESPONSE_BYTES:
                    result["errors"].append("response exceeds size limit")
                break
            else:
                result["errors"].append("too many redirects")
            if result["http_status"] == 200:
                result["checks"]["http_200"] = "PASS"
            # robots.txt / sitemap.xml on the final host
            base = f"{parsed.scheme}://{host}"
            for name, key in (("robots.txt", "robots_txt"), ("sitemap.xml", "sitemap")):
                try:
                    probe = client.get(f"{base}/{name}")
                    result[key] = probe.status_code == 200
                except httpx.HTTPError:
                    result[key] = False
    except httpx.HTTPError as exc:
        result["errors"].append(f"HTTP error: {exc}")
        result["checks"]["http"] = "FAIL"
    return result


def main():
    parser = argparse.ArgumentParser(description="HTTP-inspect a URL or reverify all.")
    parser.add_argument("--url", default="")
    parser.add_argument("--issue", default="")
    parser.add_argument("--reverify-all", action="store_true")
    args = parser.parse_args()
    if args.reverify_all:
        import os
        data_path = os.path.join(os.path.dirname(__file__), "..", "..",
                                 "data", "projects.json")
        with open(data_path, encoding="utf-8") as fh:
            projects = json.load(fh)["projects"]
        for project in projects:
            print(project["slug"], inspect_url(project["website_url"])["http_status"])
        return 0
    print(json.dumps(inspect_url(args.url), indent=2))
    return 0


if __name__ == "__main__":
    main()
