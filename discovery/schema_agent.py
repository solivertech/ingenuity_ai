"""
LLM-powered schema discovery — fetches a sample page, asks the LLM to
produce field extraction paths, then validates against live data.
"""

import json
import logging
import re
import urllib.parse
import urllib.robotparser
from dataclasses import asdict
from datetime import datetime, timezone

from domains.base import DomainConfig, FieldSchema
from analysis.llm import LLMAnalyzer, LLMResult

log = logging.getLogger(__name__)

DISCOVERY_SYSTEM_PROMPT = (
    "You are a web data extraction expert. Analyze the raw page data provided and produce "
    "a JSON extraction schema that maps the user's requested fields to the actual data "
    "structures present. Always prefer structured JSON paths (ld+json, __NEXT_DATA__, "
    "Apollo/GraphQL window objects) over DOM selectors. Use DOM selectors only as fallback. "
    "Output ONLY valid JSON — no explanation, no markdown code fences."
)

DISCOVERY_SCHEMA_TEMPLATE = """{
  "fields": [
    {
      "name": "<snake_case_field_name>",
      "display_name": "<Human Readable Name>",
      "json_paths": ["<primary.path>", "<fallback.path>"],
      "css_selectors": ["[data-testid='...']", ".class-name"],
      "data_type": "float|int|str|bool",
      "unit": "$|sqft|mi|",
      "required": true|false,
      "is_primary_sort": true|false
    }
  ],
  "pagination_style": "query_param|path_segment|none",
  "pagination_param": "page",
  "system_prompt_context": "You are a <domain> analyst...",
  "scoring_weights": {"<field_name>": <0-100>}
}"""


class SchemaAgent:
    def __init__(self, llm: LLMAnalyzer):
        self.llm = llm

    def discover(
        self,
        url: str,
        user_request: str,
        domain_id: str,
        display_name: str,
    ) -> DomainConfig | None:
        """
        Fetch the target URL and ask the LLM to produce a DomainConfig.
        Returns None if discovery fails.
        """
        _check_robots_txt(url)

        from scraper.browser import Browser

        with Browser() as browser:
            html = browser.get_page_content(url)

        if not html:
            log.error("SchemaAgent: failed to fetch %s", url)
            return None

        page_context = _extract_page_context(html)
        prompt = _build_discovery_prompt(url, user_request, page_context)

        result: LLMResult = self.llm.analyze([], _prompt_override=prompt)
        if not result.analysis:
            log.error("SchemaAgent: LLM returned no output")
            return None

        config = _parse_llm_response(result.analysis, url, domain_id, display_name, user_request)
        if config is None:
            log.error("SchemaAgent: could not parse LLM JSON response")
            return None

        log.info("SchemaAgent: discovered %d fields for %s", len(config.fields), domain_id)
        return config

    def validate_and_refine(
        self,
        config: DomainConfig,
        max_retries: int = 2,
    ) -> DomainConfig:
        """
        Spot-check the config against live data. Re-prompts LLM on field failures.
        Returns the (possibly refined) config.
        """
        from discovery.field_validator import spot_check
        from domains.generic.adapter import GenericAdapter

        adapter = GenericAdapter(config)

        for attempt in range(max_retries + 1):
            failures = spot_check(adapter, config)
            if not failures:
                log.info("SchemaAgent: validation passed on attempt %d", attempt + 1)
                return config
            if attempt == max_retries:
                log.warning(
                    "SchemaAgent: validation failed after %d retries; returning best effort",
                    max_retries,
                )
                return config
            log.info(
                "SchemaAgent: refining schema attempt %d — failures: %s",
                attempt + 1, failures,
            )
            config = self._refine(config, failures)
            adapter = GenericAdapter(config)

        return config

    def _refine(self, config: DomainConfig, failures: list[str]) -> DomainConfig:
        """Ask the LLM to fix fields that had high null rates."""
        failure_str = "\n".join(f"- {f}" for f in failures)
        refine_prompt = (
            f"The following fields had >50% null extraction rate on live data:\n{failure_str}\n\n"
            f"Current field definitions:\n"
            f"{json.dumps([asdict(f) for f in config.fields], indent=2)}\n\n"
            "Provide a corrected JSON 'fields' array only. Fix the json_paths and/or "
            "css_selectors for the failing fields. Output ONLY the corrected JSON array."
        )
        result = self.llm.analyze([], _prompt_override=refine_prompt)
        if not result.analysis:
            return config
        try:
            text = re.sub(r"```(?:json)?", "", result.analysis).strip()
            fields_data = json.loads(text)
            if isinstance(fields_data, list):
                config.fields = [FieldSchema(**f) for f in fields_data]
        except (json.JSONDecodeError, TypeError, KeyError):
            log.warning("SchemaAgent: could not parse refined fields response")
        return config


# ── Module-level helpers ───────────────────────────────────────────────────────

def _check_robots_txt(url: str) -> None:
    """
    Fetch robots.txt for the target domain and warn if scraping is disallowed.
    Never raises — a failed check is treated as permissive (network errors, 404s).
    """
    import requests

    try:
        parsed = urllib.parse.urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        resp = requests.get(
            robots_url,
            timeout=5,
            headers={"User-Agent": "Autospy"},
        )
        if resp.status_code != 200:
            log.debug("robots.txt not found at %s (HTTP %s)", robots_url, resp.status_code)
            return
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(resp.text.splitlines())
        if not rp.can_fetch("*", url):
            log.warning(
                "robots.txt at %s disallows scraping %s — "
                "proceeding anyway; ensure you have authorization.",
                robots_url, url,
            )
        else:
            log.debug("robots.txt permits scraping %s", url)
    except Exception as exc:
        log.debug("robots.txt check skipped for %s: %s", url, exc)

def _extract_page_context(html: str) -> str:
    """Pull structured JSON and a short HTML sample from raw page HTML."""
    parts = []

    ld_blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL,
    )
    if ld_blocks:
        parts.append("=== ld+json blocks ===\n" + "\n---\n".join(ld_blocks[:5]))

    m = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html, re.DOTALL,
    )
    if m:
        parts.append("=== __NEXT_DATA__ (first 6000 chars) ===\n" + m.group(1)[:6000])

    window_vars = re.findall(r'window\.__\w+\s*=\s*(\{.*?\});', html, re.DOTALL)
    if window_vars:
        parts.append(
            "=== window vars (first 3000 chars each) ===\n"
            + "\n---\n".join(v[:3000] for v in window_vars[:3])
        )

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        body_text = soup.get_text(separator=" ", strip=True)[:3000]
    except Exception:
        body_text = html[:3000]
    parts.append("=== Page text sample ===\n" + body_text)

    return "\n\n".join(parts)[:15000]


def _build_discovery_prompt(url: str, user_request: str, page_context: str) -> str:
    return (
        f"[SYSTEM]\n{DISCOVERY_SYSTEM_PROMPT}\n\n"
        f"[TARGET URL]\n{url}\n\n"
        f"[USER REQUEST]\n{user_request}\n\n"
        f"[PAGE DATA]\n{page_context}\n\n"
        f"[OUTPUT SCHEMA]\nProduce JSON matching this structure:\n{DISCOVERY_SCHEMA_TEMPLATE}"
    )


def _parse_llm_response(
    text: str,
    url: str,
    domain_id: str,
    display_name: str,
    user_request: str,
) -> DomainConfig | None:
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    try:
        fields = [FieldSchema(**f) for f in data.get("fields", [])]
        return DomainConfig(
            domain_id=domain_id,
            display_name=display_name,
            base_url=url,
            pagination_style=data.get("pagination_style", "query_param"),
            pagination_param=data.get("pagination_param", "page"),
            fields=fields,
            scoring_weights=data.get("scoring_weights", {}),
            system_prompt_context=data.get("system_prompt_context", ""),
            user_request=user_request,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    except (TypeError, KeyError) as exc:
        log.warning("SchemaAgent: parse error: %s", exc)
        return None
