from src.inspection.security_inspector import (
    check_url_safe, is_blocked_ip, revalidate_redirect_url)


def test_blocks_localhost():
    safe, _ = check_url_safe("http://localhost/admin")
    assert not safe
    safe, _ = check_url_safe("http://127.0.0.1:8080/")
    assert not safe


def test_blocks_private_ranges():
    for ip in ("10.0.0.5", "192.168.1.1", "172.16.0.9"):
        assert is_blocked_ip(ip), ip


def test_blocks_cloud_metadata():
    assert is_blocked_ip("169.254.169.254")
    safe, _ = check_url_safe("http://169.254.169.254/latest/meta-data/")
    assert not safe


def test_blocks_non_http_schemes():
    safe, _ = check_url_safe("file:///etc/passwd")
    assert not safe
    safe, _ = check_url_safe("gopher://example.com/")
    assert not safe


def test_public_ip_not_blocked():
    assert not is_blocked_ip("93.184.216.34")  # example.com
    assert not is_blocked_ip("8.8.8.8")


def test_redirect_revalidation_blocks_private():
    safe, _ = revalidate_redirect_url("http://10.1.2.3/evil")
    assert not safe
