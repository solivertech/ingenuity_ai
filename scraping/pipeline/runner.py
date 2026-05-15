"""
Pipeline runner — executes dedup → filter → enrich in sequence.
"""

import logging
from dataclasses import dataclass, field

from scraping.pipeline.normalizer import DomainItemNormalizer
from scraping.pipeline.deduplicator import Deduplicator
from scraping.pipeline.filter_engine import FilterEngine
from scraping.pipeline.enricher import GenericEnricher

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    raw_count: int = 0
    deduped_count: int = 0
    filtered_count: int = 0
    enriched: list[dict] = field(default_factory=list)


class PipelineRunner:
    """Runs items through the standard generic processing pipeline."""

    def __init__(self, domain_config=None):
        self.domain_config = domain_config
        self.normalizer = DomainItemNormalizer(domain_config)
        self.deduplicator = Deduplicator()
        self.filter_engine = FilterEngine(domain_config)
        self.enricher = GenericEnricher(domain_config)

    def run(self, items: list[dict], profile_rules: list[dict] | None = None) -> PipelineResult:
        result = PipelineResult(raw_count=len(items))

        normalized = self.normalizer.normalize_many(items)

        deduped = self.deduplicator.deduplicate(normalized, self.domain_config)
        result.deduped_count = len(deduped)

        filtered = self.filter_engine.apply(deduped, profile_rules)
        result.filtered_count = len(filtered)

        enriched = self.enricher.enrich(filtered)
        result.enriched = enriched

        log.info(
            "Pipeline: %d raw → %d normalized → %d deduped → %d filtered → %d enriched",
            result.raw_count, len(normalized), result.deduped_count,
            result.filtered_count, len(enriched),
        )
        return result
