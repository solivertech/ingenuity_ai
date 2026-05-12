"""
Domain adapter abstraction layer.

DomainAdapter is the base class for all site-specific scraping adapters.
DomainConfig + FieldSchema describe what to extract and how to score it.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class FieldSchema:
    """Describes one field to extract from a listing."""
    name: str
    display_name: str
    json_paths: list[str]
    css_selectors: list[str]
    data_type: str                   # "float" | "int" | "str" | "bool"
    unit: str = ""                   # "$", "sqft", "mi", "" etc.
    required: bool = False
    is_primary_sort: bool = False


@dataclass
class DomainConfig:
    """Complete description of a scrapeable domain. Persisted as JSON."""
    domain_id: str
    display_name: str
    base_url: str
    pagination_style: str            # "query_param" | "path_segment" | "none"
    pagination_param: str
    max_pages: int = 10
    fields: list[FieldSchema] = field(default_factory=list)
    filter_rules: list[dict] = field(default_factory=list)
    scoring_weights: dict[str, float] = field(default_factory=dict)
    system_prompt_context: str = ""
    alert_on_new: bool = True
    alert_on_drop_pct: float = 5.0
    created_at: str = ""
    user_request: str = ""


class DomainAdapter(ABC):
    """
    Base class for all domain-specific scraping adapters.
    Encapsulates URL construction and raw→normalized field mapping.
    """

    @property
    @abstractmethod
    def domain_config(self) -> DomainConfig:
        """Return the DomainConfig for this adapter."""

    @abstractmethod
    def build_url(self, page: int = 1, **filters) -> str:
        """Build the URL for a given page of results."""

    @abstractmethod
    def normalize(self, raw: dict, strategy: str) -> dict | None:
        """
        Convert a raw extracted dict into the standard listing schema.
        Return None if the listing is invalid (missing required fields).
        """

    def get_field(self, raw: dict, schema: FieldSchema):
        """Default field extraction via json_paths. Subclasses may override."""
        for path in schema.json_paths:
            val = _json_path_get(raw, path)
            if val is not None:
                return _coerce(val, schema.data_type)
        return None


# ── Utility functions ─────────────────────────────────────────────────────────

def _json_path_get(obj: dict, path: str):
    """
    Simple dot-notation path getter.
    Supports: "offers.price", "$.listing.listPrice", "mileageFromOdometer"
    """
    path = path.lstrip("$.")
    parts = path.split(".")
    cur = obj
    for part in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur


def _coerce(val, data_type: str):
    try:
        if data_type == "float":
            return float(str(val).replace(",", "").replace("$", "").strip())
        if data_type == "int":
            return int(str(val).replace(",", "").strip())
        if data_type == "bool":
            return bool(val)
        return str(val).strip()
    except (ValueError, TypeError):
        return None
