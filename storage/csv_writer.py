"""
CSV output — writes a timestamped file and overwrites a latest.csv.

For automotive profiles the column list is fixed (backward compat).
For generic domains the columns are derived from domain_config.fields.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path

import config

log = logging.getLogger(__name__)

_AUTOMOTIVE_COLUMNS = [
    "run_id", "scraped_at", "year", "make", "model", "trim", "price", "mileage",
    "monthly_carvana", "monthly_estimated",
    "price_per_mile", "value_score", "is_hybrid", "is_alert", "price_drop_pct",
    "vin", "url", "llm_backend_used", "extraction_strategy",
    "color_exterior",
]

# Columns always prepended/appended for any domain
_COMMON_PREFIX = ["run_id", "scraped_at"]
_COMMON_SUFFIX = ["value_score", "url", "llm_backend_used", "extraction_strategy"]


def write_results(
    listings: list[dict],
    run_id: str,
    llm_backend: str = "none",
    domain_config=None,
) -> Path:
    """
    Write two CSV files:
      1. Timestamped: <domain_id>_YYYYMMDD_HHMMSS.csv
      2. Latest:      <domain_id>_latest.csv (always overwritten)

    Returns the path of the timestamped file.
    """
    out_dir = Path(config.OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    if domain_config is not None:
        domain_id = domain_config.domain_id
        columns   = _columns_for_domain(domain_config)
    else:
        domain_id = "carvana"
        columns   = _AUTOMOTIVE_COLUMNS

    timestamp        = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_path = out_dir / f"{domain_id}_{timestamp}.csv"
    latest_path      = out_dir / f"{domain_id}_latest.csv"

    rows = [_build_row(listing, run_id, llm_backend, columns) for listing in listings]

    for path in (timestamped_path, latest_path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    log.info(
        "Saved %d listings -> %s (and %s_latest.csv)",
        len(listings), timestamped_path.name, domain_id,
    )
    return timestamped_path


def _columns_for_domain(domain_config) -> list[str]:
    """Derive CSV columns from a DomainConfig's fields list."""
    field_names = [f.name for f in domain_config.fields]
    cols = list(_COMMON_PREFIX)
    for name in field_names:
        if name not in cols:
            cols.append(name)
    for name in _COMMON_SUFFIX:
        if name not in cols:
            cols.append(name)
    return cols


def _build_row(listing: dict, run_id: str, llm_backend: str, columns: list[str]) -> dict:
    row = {col: listing.get(col, "") for col in columns}
    row["run_id"]           = run_id
    row["llm_backend_used"] = llm_backend
    if "is_hybrid" in listing and "is_hybrid" in columns:
        row["is_hybrid"] = int(bool(listing["is_hybrid"]))
    return row
