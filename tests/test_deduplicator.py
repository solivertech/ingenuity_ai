"""Tests for scraping.pipeline.deduplicator.Deduplicator."""

import pytest
from scraping.pipeline.deduplicator import Deduplicator


def _item(**kwargs):
    return dict(kwargs)


def _cfg(field_names):
    """Minimal domain config with named fields."""
    class _Field:
        def __init__(self, name):
            self.name = name
    class _Cfg:
        fields = [_Field(n) for n in field_names]
    return _Cfg()


# ── No duplicates ─────────────────────────────────────────────────────────────

def test_no_duplicates_returns_all():
    dd = Deduplicator()
    items = [_item(vin="A"), _item(vin="B"), _item(vin="C")]
    assert dd.deduplicate(items) == items


def test_empty_input_returns_empty():
    assert Deduplicator().deduplicate([]) == []


# ── VIN deduplication ─────────────────────────────────────────────────────────

def test_duplicate_vins_removed():
    items = [_item(vin="A", price=100), _item(vin="A", price=200), _item(vin="B")]
    result = Deduplicator().deduplicate(items)
    assert len(result) == 2
    assert result[0]["vin"] == "A"
    assert result[0]["price"] == 100  # first seen wins


def test_preserves_insertion_order():
    items = [_item(vin="C"), _item(vin="A"), _item(vin="B")]
    result = Deduplicator().deduplicate(items)
    assert [r["vin"] for r in result] == ["C", "A", "B"]


# ── URL fallback ──────────────────────────────────────────────────────────────

def test_url_used_as_id_when_no_vin():
    items = [
        _item(url="http://a.com/1", price=100),
        _item(url="http://a.com/1", price=200),
        _item(url="http://a.com/2", price=300),
    ]
    result = Deduplicator().deduplicate(items)
    assert len(result) == 2


# ── Hash fallback (no ID field at all) ───────────────────────────────────────

def test_identical_items_deduplicated_by_hash():
    item = _item(price=100, name="foo")
    result = Deduplicator().deduplicate([item, item.copy()])
    assert len(result) == 1


def test_different_items_no_id_field_both_kept():
    items = [_item(price=100), _item(price=200)]
    result = Deduplicator().deduplicate(items)
    assert len(result) == 2


# ── Domain config ID detection ────────────────────────────────────────────────

def test_domain_config_field_used_as_id():
    cfg = _cfg(["listing_id", "price"])
    items = [
        _item(listing_id="X1", price=100),
        _item(listing_id="X1", price=200),
        _item(listing_id="X2", price=300),
    ]
    result = Deduplicator().deduplicate(items, domain_config=cfg)
    assert len(result) == 2


# ── Explicit id_fields override ───────────────────────────────────────────────

def test_explicit_id_field_overrides_config():
    dd = Deduplicator(id_fields=["name"])
    items = [_item(name="foo", price=1), _item(name="foo", price=2), _item(name="bar", price=3)]
    result = dd.deduplicate(items)
    assert len(result) == 2
