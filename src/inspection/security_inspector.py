"""SSRF and abuse guards for the inspection worker.

A public GitHub issue is untrusted input. Inspection must never fetch
localhost, private networks, link-local/cloud-metadata addresses, or
follow a redirect into them. DNS is revalidated after every redirect.
"""
import ipaddress
import socket

BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # loopback
    ipaddress.ip_network("10.0.0.0/8"),       # private
    ipaddress.ip_network("172.16.0.0/12"),    # private
    ipaddress.ip_network("192.168.0.0/16"),   # private
    ipaddress.ip_network("169.254.0.0/16"),   # link-local incl. 169.254.169.254 metadata
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 private
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5


def is_blocked_ip(ip_str):
    """True if the IP is loopback, private, link-local, reserved or multicast."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable: treat as unsafe
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved \
            or ip.is_multicast or ip.is_unspecified:
        return True
    return any(ip in net for net in BLOCKED_NETWORKS)


def resolve_host(host):
    """Resolve a hostname; return (ips, blocked) with blocked IPs flagged."""
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return [], True
    ips = sorted({info[4][0] for info in infos})
    blocked = any(is_blocked_ip(ip) for ip in ips)
    return ips, blocked


def check_url_safe(url):
    """Return (safe, reason). Safe means: http(s), public DNS, no blocked IP."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url or "")
    except Exception:
        return False, "unparseable URL"
    if parsed.scheme not in ("http", "https"):
        return False, f"disallowed scheme: {parsed.scheme}"
    host = parsed.hostname
    if not host:
        return False, "missing host"
    if host in ("localhost",) or host.endswith(".local"):
        return False, "localhost/local host blocked"
    ips, blocked = resolve_host(host)
    if not ips:
        return False, "DNS resolution failed"
    if blocked:
        return False, f"host resolves to blocked IP: {', '.join(ips)}"
    return True, "ok"


def revalidate_redirect_url(url):
    """Re-check a redirect target before following it (SSRF guard)."""
    return check_url_safe(url)
