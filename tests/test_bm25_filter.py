"""Tests for scraping.discovery.bm25_filter."""

import pytest
from scraping.discovery.bm25_filter import filter_by_relevance, _split_sections, _tokenize


# ── _tokenize ─────────────────────────────────────────────────────────────────

def test_tokenize_lowercases():
    tokens = _tokenize("Hello WORLD")
    assert "hello" in tokens
    assert "world" in tokens


def test_tokenize_extracts_numbers():
    tokens = _tokenize("price 99 sale")
    assert "99" in tokens


def test_tokenize_empty_string():
    assert _tokenize("") == []


def test_tokenize_strips_punctuation():
    tokens = _tokenize("price: $99.00, discount!")
    assert "price" in tokens
    assert "discount" in tokens


def test_tokenize_returns_list():
    assert isinstance(_tokenize("hello"), list)


# ── _split_sections ───────────────────────────────────────────────────────────

def test_split_sections_by_h1():
    text = "# Section One\ncontent here\n\n# Section Two\nmore content"
    sections = _split_sections(text)
    assert len(sections) >= 2


def test_split_sections_by_h2():
    text = "## Alpha\nalpha content\n\n## Beta\nbeta content"
    sections = _split_sections(text)
    assert len(sections) >= 2


def test_split_sections_long_block_splits_on_blank_lines():
    long_para = "word " * 120
    text = long_para + "\n\n" + long_para
    sections = _split_sections(text)
    assert len(sections) >= 2


def test_split_sections_empty_text():
    assert _split_sections("") == []


def test_split_sections_returns_list():
    assert isinstance(_split_sections("hello world"), list)


# ── filter_by_relevance ────────────────────────────────────────────────────────

def test_empty_text_returns_empty():
    assert filter_by_relevance("", "price") == ""


def test_empty_query_returns_original_text():
    text = "some content here"
    assert filter_by_relevance(text, "") == text


def test_none_text_returns_original():
    assert filter_by_relevance(None, "price") is None


def test_returns_string_for_normal_input():
    result = filter_by_relevance("# Section\ncontent here", "content")
    assert isinstance(result, str)


def test_relevant_section_included():
    text = (
        "# Cars for Sale\n" + "red car blue car green car " * 20 + "\n\n"
        "# Baking Tips\n" + "flour sugar butter eggs " * 20
    )
    result = filter_by_relevance(text, "car sale", top_n=1)
    assert "car" in result.lower()


def test_irrelevant_section_excluded_when_top_n_is_1():
    text = (
        "# Cars for Sale\n" + "red car blue car green car " * 20 + "\n\n"
        "# Baking Tips\n" + "flour sugar butter eggs " * 20
    )
    result = filter_by_relevance(text, "car sale", top_n=1)
    assert "flour" not in result


def test_top_n_limits_output_sections():
    sections = [f"# Section {i}\n" + f"keyword{i} " * 30 for i in range(8)]
    text = "\n".join(sections)
    result = filter_by_relevance(text, "section", top_n=2)
    section_count = result.count("Section")
    assert section_count <= 4  # top 2 sections; some overlap in text is ok


def test_single_section_returned_intact():
    text = "only one section here with some words"
    result = filter_by_relevance(text, "words", top_n=5)
    assert "one section" in result


def test_query_with_no_match_still_returns_something():
    text = "# Listings\nprice 100\nprice 200\nprice 300"
    result = filter_by_relevance(text, "xyzabc_nomatch", top_n=5)
    assert isinstance(result, str)
    assert len(result) > 0
