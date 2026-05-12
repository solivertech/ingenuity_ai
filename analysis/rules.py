"""
Rule-based filtering and scoring.

Runs on every listing before any LLM is called — fast, free, deterministic.
"""

import logging
from collections import defaultdict

import config
from utils.payment_calc import (
    estimate_monthly_payment,
    price_per_mile as calc_price_per_mile,
)

log = logging.getLogger(__name__)

_HYBRID_KEYWORDS = {"hybrid", "hev", "phev", "prime"}

# Default year bounds used only as fallback in enrich_listing when called without profile context.
_SCORE_MIN_YEAR = 2021
_SCORE_MAX_YEAR = 2025


# ── Filtering ─────────────────────────────────────────────────────────────────

def apply_filters(
    listings: list[dict],
    max_price: int | None,
    max_mileage: int,
    min_year: int,
    max_year: int,
    excluded_trim_keywords: list[str] | None = None,
    excluded_years: list[int] | None = None,
) -> list[dict]:
    """
    Remove listings that:
    - have no price
    - exceed max_price
    - exceed max_mileage
    - are outside min_year / max_year range
    - match any year in excluded_years
    - contain any excluded_trim_keywords in their trim (case-insensitive)
    Logs how many were removed and why.
    """
    removed = defaultdict(int)
    kept = []
    _excluded = [k.lower() for k in (excluded_trim_keywords or [])]
    _excluded_years = set(excluded_years or [])

    for listing in listings:
        price   = listing.get("price")
        mileage = listing.get("mileage")
        year    = listing.get("year")
        trim    = (listing.get("trim") or "").lower()

        if listing.get("purchase_in_progress"):
            removed["purchase_in_progress"] += 1
            continue
        if not price or price <= 0:
            removed["no_price"] += 1
            continue
        if max_price is not None and price > max_price:
            removed["over_price"] += 1
            continue
        if mileage is not None and mileage > max_mileage:
            removed["over_mileage"] += 1
            continue
        if year is not None and year < min_year:
            removed["under_year"] += 1
            continue
        if year is not None and year > max_year:
            removed["over_year"] += 1
            continue
        if year is not None and year in _excluded_years:
            removed["excluded_year"] += 1
            continue
        if _excluded and any(kw in trim for kw in _excluded):
            removed["excluded_trim"] += 1
            continue

        kept.append(listing)

    total_removed = sum(removed.values())
    if total_removed:
        reasons = ", ".join(f"{k}={v}" for k, v in removed.items())
        log.info(
            "Filtered out %d listings (%s) — %d remain",
            total_removed, reasons, len(kept),
        )
    else:
        log.info("No listings filtered — all %d passed", len(kept))

    return kept


# ── Enrichment ────────────────────────────────────────────────────────────────

def enrich_listings(
    listings: list[dict],
    max_year: int,
    max_mileage: int = 80000,
    min_year: int = _SCORE_MIN_YEAR,
    model_preference: list[str] | None = None,
    hybrid_bonus: bool = True,
    down_payment: int | None = None,
    scoring_weights: dict | None = None,
) -> list[dict]:
    """
    Enrich all listings in-place, computing value scores that require
    group averages across the full dataset first.
    Returns the same list (mutated).
    """
    group_averages = _compute_group_averages(listings)

    enriched = [
        enrich_listing(
            listing, group_averages,
            current_year=max_year,
            max_mileage=max_mileage,
            min_year=min_year,
            model_preference=model_preference or [],
            hybrid_bonus=hybrid_bonus,
            down_payment=down_payment,
            scoring_weights=scoring_weights,
        )
        for listing in listings
    ]
    return enriched


def enrich_listing(
    listing: dict,
    group_averages: dict | None = None,
    current_year: int = _SCORE_MAX_YEAR,
    max_mileage: int = 80000,
    min_year: int = _SCORE_MIN_YEAR,
    model_preference: list[str] | None = None,
    hybrid_bonus: bool = True,
    down_payment: int | None = None,
    scoring_weights: dict | None = None,
) -> dict:
    """
    Add computed fields to a listing dict:
      - monthly_estimated
      - price_per_mile
      - is_hybrid
      - age_years
      - value_score
    """
    price   = listing.get("price") or 0.0
    mileage = listing.get("mileage")
    year    = listing.get("year")
    trim    = listing.get("trim") or ""

    listing["monthly_estimated"] = estimate_monthly_payment(
        price,
        down_payment if down_payment is not None else config.DOWN_PAYMENT,
        config.INTEREST_RATE,
        config.LOAN_TERM_MONTHS,
    )
    listing["price_per_mile"] = calc_price_per_mile(price, mileage)
    listing["is_hybrid"]      = _is_hybrid(trim)
    listing["age_years"]      = (current_year - year) if year else None
    listing["value_score"]    = _value_score(
        listing, group_averages or {}, current_year, max_mileage,
        min_year=min_year,
        model_preference=model_preference or [],
        hybrid_bonus=hybrid_bonus,
        scoring_weights=scoring_weights,
    )
    return listing


# ── Value score ───────────────────────────────────────────────────────────────

_DEFAULT_WEIGHTS = {"price": 35, "mileage": 25, "age": 20, "shipping": 10, "hybrid": 10}


def _value_score(
    listing: dict,
    group_averages: dict,
    current_year: int,
    max_mileage: int = 80000,
    min_year: int = _SCORE_MIN_YEAR,
    model_preference: list[str] | None = None,
    hybrid_bonus: bool = True,
    scoring_weights: dict | None = None,
) -> float:
    """
    Produce a 0–100 score. Higher is better.

    Weight keys (from scoring_weights or _DEFAULT_WEIGHTS):
      price    — price vs group average (same make/model/year)
      mileage  — inverse linear, 0→full pts, max_mileage→0pts
      age      — newer = better, max_year→full pts, min_year→0pts
      shipping — free/unknown→full pts, $1,500+→0pts, linear
      hybrid   — bonus when listing is_hybrid (only when hybrid_bonus=True)
    Plus up to 6 pts model preference bonus (auto-spread by rank).
    """
    w = scoring_weights if scoring_weights is not None else _DEFAULT_WEIGHTS

    price    = listing.get("price") or 0.0
    mileage  = listing.get("mileage")
    year     = listing.get("year")
    shipping = listing.get("shipping")

    w_price    = w.get("price",    35)
    w_mileage  = w.get("mileage",  25)
    w_age      = w.get("age",      20)
    w_shipping = w.get("shipping", 10)
    w_hybrid   = w.get("hybrid",   10)

    # ── Price component ───────────────────────────────────────────────────────
    group_key = (listing.get("make"), listing.get("model"), year)
    avg_price = group_averages.get(group_key)
    if avg_price and avg_price > 0:
        pct_diff = (avg_price - price) / avg_price * 100
        pct_diff = max(-30.0, min(30.0, pct_diff))
        price_score = ((pct_diff + 30) / 60) * w_price
    else:
        price_score = w_price / 2  # neutral when no group data

    # ── Mileage component ─────────────────────────────────────────────────────
    if mileage is None:
        mileage_score = w_mileage / 2
    else:
        mileage_score = max(0.0, w_mileage * (1 - mileage / max_mileage))

    # ── Age component — uses profile's year range as floor/ceiling ────────────
    year_range = max(1, current_year - min_year)
    if year is None:
        age_score = w_age / 2
    else:
        clamped = max(min_year, min(current_year, year))
        age_score = ((clamped - min_year) / year_range) * w_age

    # ── Shipping component — free/unknown = full; $1,500+ = 0 ────────────────
    _MAX_SHIP = 1500.0
    if shipping is None:
        shipping_score = w_shipping
    else:
        shipping_score = max(0.0, w_shipping * (1 - shipping / _MAX_SHIP))

    # ── Hybrid bonus (optional) ───────────────────────────────────────────────
    hybrid_score = (w_hybrid if listing.get("is_hybrid") else 0.0) if hybrid_bonus else 0.0

    # ── Model preference bonus (up to 6 pts, auto-spread by rank) ────────────
    model_score = _model_preference_bonus(listing.get("model") or "", model_preference or [])

    total = price_score + mileage_score + age_score + shipping_score + hybrid_score + model_score
    return round(min(100.0, max(0.0, total)), 2)


def _model_preference_bonus(model: str, preference_order: list[str], max_bonus: float = 6.0) -> float:
    """
    Compute a 0–max_bonus score based on where model ranks in preference_order.
    First model = max_bonus, last = 0, evenly spread. Unknown models = 0.
    Empty preference list = 0 for all (no bias).
    """
    n = len(preference_order)
    if n <= 1:
        return 0.0
    try:
        rank = preference_order.index(model)
        return max_bonus * (n - 1 - rank) / (n - 1)
    except ValueError:
        return 0.0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_hybrid(trim: str) -> bool:
    trim_lower = trim.lower()
    return any(kw in trim_lower for kw in _HYBRID_KEYWORDS)


def _compute_group_averages(listings: list[dict]) -> dict:
    """
    Return a dict mapping (make, model, year) → average price
    across all listings in the dataset.
    """
    groups: dict[tuple, list[float]] = defaultdict(list)
    for listing in listings:
        price = listing.get("price")
        if price:
            key = (listing.get("make"), listing.get("model"), listing.get("year"))
            groups[key].append(price)
    return {key: sum(prices) / len(prices) for key, prices in groups.items()}
