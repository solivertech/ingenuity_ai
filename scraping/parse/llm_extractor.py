"""
LLM-based field extraction — Strategy 5 (last resort).

Cleans HTML to Markdown, then uses the LLM to extract fields matching
the domain config schema. Only invoked when all other strategies fail.
"""

import json
import logging

from scraping.parse.html_cleaner import HTMLCleaner

log = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
Extract the following fields from this page content.

FIELDS TO EXTRACT:
{fields_json}

PAGE CONTENT:
{page_markdown}

Rules:
- Return only fields that are clearly present in the content.
- Do not infer or calculate values. Extract only what is explicitly stated.
- For numbers, strip currency symbols and commas. Return bare numbers.
- For dates, return ISO 8601 format (YYYY-MM-DD).
- If a field is not found, omit it from the response.

Return ONLY valid JSON. No explanation. No markdown code blocks.
Format: {{"field_name": value, ...}}\
"""

_cleaner = HTMLCleaner()
_MAX_MARKDOWN_CHARS = 8000


class LLMExtractor:
    """Extracts structured data from page HTML using the LLM as a last resort."""

    def extract(self, html: str, domain_config) -> list[dict]:
        """Return a list of item dicts extracted by the LLM (usually one per page)."""
        if not domain_config or not domain_config.fields:
            return []

        markdown = _cleaner.clean(html)
        if not markdown:
            return []

        if len(markdown) > _MAX_MARKDOWN_CHARS:
            markdown = markdown[:_MAX_MARKDOWN_CHARS] + "\n\n[content truncated]"

        fields_spec = [
            {
                "name": f.name,
                "display_name": f.display_name,
                "data_type": f.data_type,
                "unit": f.unit or "",
                "required": f.required,
            }
            for f in domain_config.fields
        ]

        prompt = _EXTRACTION_PROMPT.format(
            fields_json=json.dumps(fields_spec, indent=2),
            page_markdown=markdown,
        )

        try:
            result = self._call_llm(prompt)
            if result:
                return [result]
        except Exception as exc:
            log.warning("LLM extraction failed: %s", exc)

        return []

    def _call_llm(self, prompt: str) -> dict | None:
        try:
            import config
            if not (getattr(config, "ANTHROPIC_ENABLED", False)
                    and getattr(config, "ANTHROPIC_API_KEY", "")):
                return None
            import anthropic
            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            msg = client.messages.create(
                model=getattr(config, "ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(msg.content[0].text.strip())
        except Exception as exc:
            log.debug("LLM call failed: %s", exc)
            return None
