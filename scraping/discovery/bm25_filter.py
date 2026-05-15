"""
BM25 content filtering — ranks Markdown sections by relevance to user intent.

Used by SchemaAgent to trim page content before sending to the LLM.
Reduces token usage and improves extraction accuracy by keeping only the
most relevant sections.
"""

import logging
import re

log = logging.getLogger(__name__)


def filter_by_relevance(text: str, query: str, top_n: int = 10) -> str:
    """
    Split text into sections, rank by BM25 relevance to query,
    and return the top_n sections concatenated.
    Falls back to the full text if rank_bm25 is unavailable.
    """
    if not text or not query:
        return text

    sections = _split_sections(text)
    if not sections:
        return text

    try:
        from rank_bm25 import BM25Okapi
        tokenized = [_tokenize(s) for s in sections]
        bm25 = BM25Okapi(tokenized)
        scores = bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(scores, sections), key=lambda x: x[0], reverse=True)
        top = [s for _, s in ranked[:top_n]]
        log.debug("BM25: kept %d/%d sections for query=%r", len(top), len(sections), query[:60])
        return "\n\n".join(top)
    except ImportError:
        log.debug("rank_bm25 not installed — returning full content")
        return text


def _split_sections(text: str) -> list[str]:
    parts = re.split(r"(?m)^#{1,3}\s+", text)
    sections: list[str] = []
    for part in parts:
        if len(part) > 500:
            for sub in part.split("\n\n"):
                sub = sub.strip()
                if sub:
                    sections.append(sub)
        elif part.strip():
            sections.append(part.strip())
    return sections


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())
