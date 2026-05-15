"""
Reference doc generation.
Tries NVIDIA NIM first, falls back to Cerebras.
Used by both the desktop (/docs/generate) and portal (/portal/docs/generate) routers.
"""

import config

_NVIDIA_BASE_URL   = "https://integrate.api.nvidia.com/v1"
_CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"

def _build_automotive_prompt(
    topic: str,
    description: str,
    make: str,
    model: str,
    year_start: int,
    year_end: int,
) -> str:
    years = f"{year_start}–{year_end}"
    header = f"{years} {make} {model}" if (make and model) else topic
    context_line = f"\nAdditional context: {description.strip()}" if description.strip() else ""
    return f"""Generate a comprehensive vehicle reference guide for the {header} in Markdown format.

This document will be fed to an AI system to help evaluate used car listings. Be specific, accurate, and practical.

Structure the document exactly as shown:

# {header} Reference Guide — Listing Evaluation Context

## Part 1 — Model Overview & Reliability
Covered generation(s), reliability summary, engine options, MPG (city/highway), cargo space, towing capacity.

## Part 2 — Trim Level Reference
Markdown table with columns: Trim | Years | Type (Gas/Hybrid/PHEV) | MPG | Key Features | Notes

## Part 3 — Pricing Context
Expected used pricing by year and trim for {years}. Note significant value cliffs between years.

## Part 4 — Common Issues & Recalls
Known reliability problems, TSBs, and recalls for this generation. Be specific about which years/mileage are affected.

## Part 5 — Evaluation Tips
How to identify trims from a listing description, what to look for, red flags to avoid.{context_line}

Focus only on the {years} generation. Include hybrid/PHEV variants if they exist for this vehicle."""


def _build_generic_prompt(topic: str, description: str) -> str:
    context_block = f"\n\nContext from the user:\n{description.strip()}" if description.strip() else ""
    return f"""Generate a comprehensive reference guide for: **{topic}**

This document will be used by an AI system to help evaluate, compare, and score listings or options. Be specific, accurate, and practical. Write in Markdown.

Structure the document as follows:

# {topic} — Reference Guide

## Overview
What this is, key characteristics, and why it matters for evaluation.

## Key Specifications / Features to Look For
The most important attributes, specs, or qualities — and what values are considered good, average, or poor.

## Common Variants / Options / Configurations
Major variants, tiers, or configurations that a buyer might encounter. Note differences that significantly affect value or suitability.

## Pricing Context
Typical price ranges and what drives value up or down. Flag when something is priced too high or suspiciously low.

## Red Flags / Things to Avoid
Specific issues, defects, warning signs, or deal-breakers to watch out for in listings.

## Evaluation Tips
Practical advice for assessing listings: what to read carefully, what photos to look for, questions to ask, and how to score options against each other.{context_block}

Be thorough but concise. Prioritize information that helps compare and rank options rather than general background knowledge."""


def build_prompt(
    topic: str,
    description: str,
    domain_id: str | None = None,
    extra: dict | None = None,
) -> str:
    extra = extra or {}
    make  = str(extra.get("make", "")).strip()
    model = str(extra.get("model", "")).strip()
    if make or model:
        year_start = int(extra.get("year_start", 2020))
        year_end   = int(extra.get("year_end", 2025))
        return _build_automotive_prompt(topic, description, make, model, year_start, year_end)
    return _build_generic_prompt(topic, description)


def generate_doc(
    topic: str,
    description: str = "",
    domain_id: str | None = None,
    extra: dict | None = None,
) -> str:
    """
    Generate a reference markdown doc. Tries NVIDIA NIM first, Cerebras as fallback.
    Returns the content string.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed — run: pip install openai")

    prompt = build_prompt(topic, description, domain_id, extra)

    # ── Primary: NVIDIA NIM ───────────────────────────────────────────────────
    if config.NVIDIA_API_KEY:
        try:
            client = OpenAI(api_key=config.NVIDIA_API_KEY, base_url=_NVIDIA_BASE_URL)
            response = client.chat.completions.create(
                model=config.NVIDIA_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "NVIDIA NIM doc generation failed: %s — falling back to Cerebras", exc
            )

    # ── Fallback: Cerebras ────────────────────────────────────────────────────
    if not config.CEREBRAS_API_KEY:
        raise ValueError(
            "NVIDIA_API_KEY and CEREBRAS_API_KEY are both unconfigured — add at least one to .env"
        )
    client = OpenAI(api_key=config.CEREBRAS_API_KEY, base_url=_CEREBRAS_BASE_URL)
    response = client.chat.completions.create(
        model=config.CEREBRAS_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


# Keep the old entry point working (used by portal router)
def generate_vehicle_doc(make: str, model_name: str, year_start: int, year_end: int, notes: str = "") -> str:
    topic = f"{make} {model_name}" if make and model_name else make or model_name
    return generate_doc(
        topic=topic,
        description=notes,
        domain_id="carvana_suvs",
        extra={"make": make, "model": model_name, "year_start": year_start, "year_end": year_end},
    )
