"""Tests for scraping.session.session_pool.SessionPool."""

import pytest
from scraping.session.session_pool import SessionPool


# ── No-proxy mode (backward-compat) ──────────────────────────────────────────

def test_no_proxies_get_proxy_returns_none():
    pool = SessionPool()
    assert pool.get_proxy() is None


def test_no_proxies_has_proxies_is_false():
    pool = SessionPool()
    assert not pool.has_proxies


def test_no_proxies_rotate_returns_none():
    pool = SessionPool()
    assert pool.rotate_proxy() is None


# ── Proxy list ────────────────────────────────────────────────────────────────

def test_single_proxy_returned():
    pool = SessionPool(proxies=["http://p1:8080"])
    assert pool.get_proxy() == "http://p1:8080"


def test_has_proxies_true_when_list_provided():
    pool = SessionPool(proxies=["http://p1:8080"])
    assert pool.has_proxies


def test_proxy_count():
    pool = SessionPool(proxies=["http://p1:8080", "http://p2:8080"])
    assert pool.proxy_count == 2


def test_get_proxy_returns_same_until_rotated():
    pool = SessionPool(proxies=["http://p1:8080", "http://p2:8080"])
    assert pool.get_proxy() == pool.get_proxy()


def test_rotate_advances_to_next_proxy():
    pool = SessionPool(proxies=["http://p1:8080", "http://p2:8080"])
    first = pool.get_proxy()
    pool.rotate_proxy()
    second = pool.get_proxy()
    assert first != second


def test_rotate_wraps_around():
    pool = SessionPool(proxies=["http://p1:8080", "http://p2:8080"])
    pool.rotate_proxy()
    pool.rotate_proxy()
    assert pool.get_proxy() == "http://p1:8080"


# ── Block tracking ────────────────────────────────────────────────────────────

def test_mark_proxy_blocked_skips_that_proxy():
    pool = SessionPool(proxies=["http://p1:8080", "http://p2:8080"])
    current = pool.get_proxy()
    pool.mark_proxy_blocked(current)
    assert pool.get_proxy() != current


def test_blocked_proxy_count():
    pool = SessionPool(proxies=["http://p1:8080", "http://p2:8080"])
    pool.mark_proxy_blocked("http://p1:8080")
    assert pool.blocked_proxy_count == 1


def test_all_blocked_resets_and_continues():
    pool = SessionPool(proxies=["http://p1:8080"])
    pool.mark_proxy_blocked("http://p1:8080")
    # All blocked — reset should clear and return p1 again
    proxy = pool.get_proxy()
    assert proxy == "http://p1:8080"


def test_mark_proxy_blocked_nonexistent_does_not_crash():
    pool = SessionPool(proxies=["http://p1:8080"])
    pool.mark_proxy_blocked("http://unknown:9999")  # should not raise
    assert pool.blocked_proxy_count == 0


# ── Legacy session API (backward-compat) ──────────────────────────────────────

def test_mark_blocked_session():
    pool = SessionPool()
    pool.mark_blocked("session-abc")
    assert pool.is_blocked("session-abc")


def test_retire_unblocks_session():
    pool = SessionPool()
    pool.mark_blocked("session-abc")
    pool.retire("session-abc")
    assert not pool.is_blocked("session-abc")


def test_is_blocked_unknown_session_returns_false():
    pool = SessionPool()
    assert not pool.is_blocked("nonexistent")


def test_mark_blocked_also_rotates_proxy():
    pool = SessionPool(proxies=["http://p1:8080", "http://p2:8080"])
    first = pool.get_proxy()
    pool.mark_blocked("session-x")
    # proxy should have advanced
    assert pool.get_proxy() != first or pool.blocked_proxy_count > 0
