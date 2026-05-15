"""Tests for alerts.change_detector.ChangeDetector."""

import pytest
from alerts.change_detector import ChangeDetector


def _item(**kwargs):
    return dict(kwargs)


# ── No previous data ──────────────────────────────────────────────────────────

def test_empty_previous_returns_nothing():
    cd = ChangeDetector(tracked_fields=["price"])
    result = cd.detect([_item(vin="A", price=100)], [])
    assert result == []


def test_no_previous_match_for_item():
    prev = [_item(vin="B", price=100)]
    curr = [_item(vin="A", price=200)]
    cd = ChangeDetector(tracked_fields=["price"])
    assert cd.detect(curr, prev) == []


# ── Change detection ──────────────────────────────────────────────────────────

def test_price_change_detected():
    prev = [_item(vin="A", price=100)]
    curr = [_item(vin="A", price=90)]
    cd = ChangeDetector(tracked_fields=["price"])
    result = cd.detect(curr, prev)
    assert len(result) == 1
    assert result[0]["changes"]["price"] == (100, 90)


def test_no_change_returns_empty():
    prev = [_item(vin="A", price=100)]
    curr = [_item(vin="A", price=100)]
    cd = ChangeDetector(tracked_fields=["price"])
    assert cd.detect(curr, prev) == []


def test_change_in_non_tracked_field_ignored():
    prev = [_item(vin="A", price=100, mileage=10000)]
    curr = [_item(vin="A", price=100, mileage=20000)]
    cd = ChangeDetector(tracked_fields=["price"])
    assert cd.detect(curr, prev) == []


def test_changed_item_is_a_copy():
    prev = [_item(vin="A", price=100)]
    curr = [_item(vin="A", price=90)]
    original = curr[0]
    cd = ChangeDetector(tracked_fields=["price"])
    result = cd.detect(curr, prev)
    assert result[0] is not original


# ── ID field resolution ───────────────────────────────────────────────────────

def test_uses_explicit_id_field():
    prev = [_item(listing_id="X1", price=100)]
    curr = [_item(listing_id="X1", price=80)]
    cd = ChangeDetector(id_field="listing_id", tracked_fields=["price"])
    result = cd.detect(curr, prev)
    assert len(result) == 1


def test_falls_back_to_url_id():
    prev = [_item(url="http://a.com/1", price=100)]
    curr = [_item(url="http://a.com/1", price=80)]
    cd = ChangeDetector(tracked_fields=["price"])
    result = cd.detect(curr, prev)
    assert len(result) == 1


def test_no_id_field_skips_item():
    prev = [_item(price=100)]
    curr = [_item(price=80)]
    cd = ChangeDetector(tracked_fields=["price"])
    assert cd.detect(curr, prev) == []


# ── Multiple items and fields ─────────────────────────────────────────────────

def test_multiple_field_changes_all_captured():
    prev = [_item(vin="A", price=100, mileage=10000)]
    curr = [_item(vin="A", price=90,  mileage=11000)]
    cd = ChangeDetector(tracked_fields=["price", "mileage"])
    result = cd.detect(curr, prev)
    assert len(result) == 1
    assert "price" in result[0]["changes"]
    assert "mileage" in result[0]["changes"]


def test_only_changed_items_returned():
    prev = [_item(vin="A", price=100), _item(vin="B", price=200)]
    curr = [_item(vin="A", price=90),  _item(vin="B", price=200)]
    cd = ChangeDetector(tracked_fields=["price"])
    result = cd.detect(curr, prev)
    assert len(result) == 1
    assert result[0]["vin"] == "A"
