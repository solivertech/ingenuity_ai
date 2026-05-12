"""
Carvana vehicle normalization.

Moved from scraper/extractor.py::normalize_vehicle.
Converts a raw extracted dict (from any extraction strategy) into the
standard automotive listing schema.
"""

import logging
import re
from datetime import datetime, timezone

from utils.vin_decode import normalize_drivetrain as _normalize_drivetrain

log = logging.getLogger(__name__)


def normalize_vehicle(raw: dict, make: str, model: str, strategy: str) -> dict | None:
    """
    Converts a raw vehicle dict (from any strategy) into the standard schema.
    Returns None if the listing is missing a price or cannot be parsed.
    """
    try:
        # ── price ─────────────────────────────────────────────────────────────
        offers = raw.get("offers") or {}
        price = (
            offers.get("price")
            or raw.get("price")
            or raw.get("listPrice")
            or raw.get("salePrice")
            or raw.get("purchasePrice")
            or 0
        )
        if isinstance(price, dict):
            price = price.get("amount") or price.get("value") or 0
        price = _to_float(price)
        if not price or price <= 0:
            return None

        # ── mileage ───────────────────────────────────────────────────────────
        mileage = (
            raw.get("mileageFromOdometer")
            or raw.get("mileage")
            or raw.get("miles")
            or raw.get("odometer")
            or None
        )
        mileage = _to_int(mileage)

        # ── year ──────────────────────────────────────────────────────────────
        year = raw.get("modelDate") or raw.get("year") or raw.get("modelYear") or None
        if year is None and raw.get("title"):
            year = _year_from_title(raw["title"])
        if year is None and raw.get("name"):
            year = _year_from_title(raw["name"])
        year = _to_int(year)

        # ── trim ──────────────────────────────────────────────────────────────
        trim = raw.get("trim") or raw.get("trimLevel") or raw.get("trimName") or ""
        if not trim:
            desc = raw.get("description") or raw.get("name") or ""
            trim = _trim_from_description(desc, make, model, year)
        if not trim and raw.get("title"):
            trim = _trim_from_title(raw["title"], make, model, year)

        # ── vin ───────────────────────────────────────────────────────────────
        vin = (
            raw.get("vehicleIdentificationNumber")
            or raw.get("vin")
            or raw.get("stockNumber")
            or raw.get("vehicleId")
            or raw.get("sku")
            or ""
        )

        # ── monthly payment ───────────────────────────────────────────────────
        monthly = (
            raw.get("monthlyPayment")
            or raw.get("estimatedMonthlyPayment")
            or raw.get("monthly")
            or None
        )
        if isinstance(monthly, dict):
            monthly = monthly.get("amount") or monthly.get("value")
        monthly = _to_float(monthly)

        # ── URL ───────────────────────────────────────────────────────────────
        url = (
            offers.get("url")
            or raw.get("slug")
            or raw.get("vehicleUrl")
            or raw.get("url")
            or ""
        )
        if url and not url.startswith("http"):
            url = f"https://www.carvana.com/vehicle/{url}"

        # ── drivetrain ────────────────────────────────────────────────────────
        drivetrain_raw = (
            raw.get("driveWheelConfiguration")
            or raw.get("driveType")
            or raw.get("drivetrain")
            or raw.get("drive")
            or raw.get("drivetrainType")
            or ""
        )
        drivetrain = _normalize_drivetrain(str(drivetrain_raw))

        # ── colours ───────────────────────────────────────────────────────────
        color_ext = (
            raw.get("exteriorColor")
            or raw.get("color")
            or raw.get("colorExterior")
            or ""
        )

        # ── purchase in progress ──────────────────────────────────────────────
        availability = (offers.get("availability") or "").lower()
        avail_not_instock = bool(availability) and "instock" not in availability

        status = (
            raw.get("status")
            or raw.get("inventoryStatus")
            or raw.get("listingStatus")
            or ""
        ).lower()
        explicit_flag = bool(
            raw.get("purchaseInProgress")
            or raw.get("purchase_in_progress")
            or raw.get("isPurchaseInProgress")
        )
        purchase_in_progress = (
            explicit_flag
            or avail_not_instock
            or "progress" in status
            or "pending"  in status
            or "reserved" in status
            or "hold"     in status
        )

        log.debug(
            "Normalized via %s: %s %s %s %s — $%s%s",
            strategy, year, make, model, trim, price,
            " [PURCHASE IN PROGRESS]" if purchase_in_progress else "",
        )

        return {
            "vin":                    str(vin),
            "year":                   year,
            "make":                   make,
            "model":                  model,
            "trim":                   str(trim).strip(),
            "price":                  price,
            "mileage":                mileage,
            "monthly_carvana":        monthly,
            "shipping":               None,
            "drivetrain":             drivetrain,
            "color_exterior":         str(color_ext).strip(),
            "url":                    url,
            "purchase_in_progress":   purchase_in_progress,
            "is_recent":              False,
            "is_carvana_price_drop":  False,
            "extraction_strategy":    strategy,
            "scraped_at":             datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        log.debug("normalize_vehicle error (%s): %s", strategy, exc)
        return None


# ── Private helpers ───────────────────────────────────────────────────────────

def _to_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return None


def _to_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _year_from_title(title: str) -> int | None:
    m = re.search(r"\b(20\d{2})\b", title)
    return int(m.group(1)) if m else None


def _trim_from_title(title: str, make: str, model: str, year: int | None) -> str:
    result = title
    for token in [str(year or ""), make, model]:
        result = result.replace(token, "")
    return result.strip()


def _trim_from_description(desc: str, make: str, model: str, year: int | None) -> str:
    """
    Extract trim from Schema.org description like:
      'Used 2021 Toyota RAV4 XLE Premium with 47863 miles - $27,990'
    """
    if not desc:
        return ""
    pattern = rf"(?:Used\s+)?{re.escape(str(year or ''))}\s*{re.escape(make)}\s*{re.escape(model)}\s*"
    result = re.sub(pattern, "", desc, flags=re.IGNORECASE).strip()
    result = re.sub(r"\s+with\s+[\d,]+\s+miles.*$", "", result, flags=re.IGNORECASE).strip()
    return result
