"""
Generic domain adapter — fully config-driven, no hardcoded field logic.

All extraction is driven by FieldSchema.json_paths and css_selectors.
Instantiated with a DomainConfig loaded from domains/saved/<id>.json.
"""

from datetime import datetime, timezone

from domains.base import DomainAdapter, DomainConfig


class GenericAdapter(DomainAdapter):
    """
    Config-driven adapter for any domain defined by a DomainConfig.
    URL construction and field normalization are entirely data-driven.
    """

    def __init__(self, config: DomainConfig):
        self._config = config

    @property
    def domain_config(self) -> DomainConfig:
        return self._config

    def build_url(self, page: int = 1, **filters) -> str:
        base = self._config.base_url.rstrip("/")
        if self._config.pagination_style == "query_param":
            sep = "&" if "?" in base else "?"
            return f"{base}{sep}{self._config.pagination_param}={page}"
        if self._config.pagination_style == "path_segment":
            return f"{base}/{page}"
        return base  # pagination_style == "none"

    def normalize(self, raw: dict, strategy: str, **kwargs) -> dict | None:
        result: dict = {
            "extraction_strategy": strategy,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        for field_schema in self._config.fields:
            val = self.get_field(raw, field_schema)
            if val is None and field_schema.required:
                return None
            result[field_schema.name] = val
        return result
