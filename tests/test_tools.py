"""
tests/test_tools.py

Pytest tests for the FitFindr tools. At least one test per failure mode.
Run with:  pytest tests/
(use the venv: .venv/Scripts/python.exe -m pytest tests/)
"""

import tools
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


# ── Tool 1: search_listings ─────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


# ── Tool 2: suggest_outfit ──────────────────────────────────────────────────

def test_suggest_outfit_empty_wardrobe():
    # Failure mode 1: empty wardrobe should still return a useful, non-empty
    # string (general advice) — never an exception or empty string.
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert result.strip() != ""


def test_suggest_outfit_llm_error_fallback(monkeypatch):
    # Failure mode 2: if the LLM call raises, return a non-empty fallback
    # string rather than crashing.
    def boom():
        raise RuntimeError("LLM unreachable")

    monkeypatch.setattr(tools, "_get_groq_client", boom)
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(result, str)
    assert result.strip() != ""


# ── Tool 3: create_fit_card ─────────────────────────────────────────────────

def test_create_fit_card_empty_outfit():
    # Failure mode 1: empty/whitespace outfit returns a descriptive error
    # string instead of calling the LLM or raising.
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = create_fit_card("", item)
    assert isinstance(result, str)
    assert result.strip() != ""
    assert "outfit" in result.lower()


def test_create_fit_card_llm_error_fallback(monkeypatch):
    # Failure mode 2: if the LLM call raises, return a non-empty fallback
    # caption rather than crashing.
    def boom():
        raise RuntimeError("LLM unreachable")

    monkeypatch.setattr(tools, "_get_groq_client", boom)
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = create_fit_card("track jacket with baggy jeans", item)
    assert isinstance(result, str)
    assert result.strip() != ""
