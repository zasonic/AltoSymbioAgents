"""tests/test_web_research_ssrf.py — adversarial SSRF matrix for web_research.

Exercises the real ``_validate_url`` (real ``ipaddress`` classification, real
DNS resolution for public/loopback names) — no monkeypatched resolver. Every
unsafe target must raise ``WebFetchError`` and fail closed.
"""

from __future__ import annotations

import pytest

from services import web_research as wr


class _Settings:
    """Minimal settings stub (real Settings is exercised elsewhere)."""
    def __init__(self, **kw):
        self._d = kw
    def get(self, key, default=None):
        return self._d.get(key, default)


def test_blocks_non_http_schemes():
    for bad in ("file:///etc/passwd", "ftp://host/x", "gopher://h/", "data:text/html,hi"):
        with pytest.raises(wr.WebFetchError) as ei:
            wr._validate_url(bad, _Settings())
        assert ei.value.reason == "blocked_scheme"


def test_blocks_loopback_and_localhost():
    for bad in ("http://127.0.0.1/", "http://127.0.0.5/", "http://localhost/", "http://[::1]/"):
        with pytest.raises(wr.WebFetchError) as ei:
            wr._validate_url(bad, _Settings())
        assert ei.value.reason == "blocked_host"


def test_blocks_private_ranges():
    for bad in ("http://10.0.0.5/", "http://192.168.1.1/", "http://172.16.0.9/"):
        with pytest.raises(wr.WebFetchError) as ei:
            wr._validate_url(bad, _Settings())
        assert ei.value.reason == "blocked_host"


def test_blocks_cloud_metadata_endpoint():
    with pytest.raises(wr.WebFetchError) as ei:
        wr._validate_url("http://169.254.169.254/latest/meta-data/", _Settings())
    assert ei.value.reason == "blocked_host"


def test_blocks_ipv4_mapped_ipv6_loopback():
    with pytest.raises(wr.WebFetchError) as ei:
        wr._validate_url("http://[::ffff:127.0.0.1]/", _Settings())
    assert ei.value.reason == "blocked_host"


def test_blocks_no_host():
    with pytest.raises(wr.WebFetchError):
        wr._validate_url("http:///nopath", _Settings())


def test_blocklist_denies_domain_and_subdomain():
    s = _Settings(web_research_blocked_domains=["evil.example"])
    for bad in ("http://evil.example/", "http://api.evil.example/x"):
        with pytest.raises(wr.WebFetchError) as ei:
            wr._validate_url(bad, s)
        assert ei.value.reason == "blocked_host"


def test_allowlist_denies_unlisted_domain():
    s = _Settings(web_research_allowed_domains=["good.example"])
    with pytest.raises(wr.WebFetchError) as ei:
        wr._validate_url("http://other.example/", s)
    assert ei.value.reason == "blocked_host"


def test_allow_private_opt_in_permits_loopback():
    # With the explicit opt-in, the IP screen is skipped (host still resolves).
    out = wr._validate_url("http://127.0.0.1:8080/docs", _Settings(web_research_allow_private=True))
    assert out == "http://127.0.0.1:8080/docs"
