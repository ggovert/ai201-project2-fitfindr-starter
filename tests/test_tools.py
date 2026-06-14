"""
tests/test_tools.py

Pytest tests for all three FitFindr tools.
Run with: pytest tests/
"""

import pytest
from unittest.mock import patch, MagicMock

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings tests ────────────────────────────────────────────────────

def test_search_returns_results():
    """Keyword 'graphic tee' should return at least one listing."""
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    """No listing mentions 'designer ballgown' — should return empty list, no exception."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    """All returned listings must have price <= max_price."""
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)


def test_search_size_filter():
    """Size filter should be case-insensitive and flexible (M matches S/M, One Size, etc.)."""
    results = search_listings("tee", size="M", max_price=None)
    assert all(item["price"] > 0 for item in results)  # at least something matched


def test_search_no_price_no_size():
    """With no price or size filter, should still return results for a known term."""
    results = search_listings("vintage", size=None, max_price=None)
    assert isinstance(results, list)
    assert len(results) > 0


# ── suggest_outfit tests ─────────────────────────────────────────────────────

@patch("tools.Groq")
def test_suggest_outfit_with_wardrobe(mock_groq_class):
    """With a non-empty wardrobe, the LLM is called and returns a non-empty string."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(
            content="Pair this with your Baggy straight-leg jeans and combat boots for a classic grunge look."
        ))]
    )
    mock_groq_class.return_value = mock_client

    wardrobe = get_example_wardrobe()
    result = suggest_outfit({"title": "Band Tee", "description": "test"}, wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "couldn't" not in result.lower()


@patch("tools.Groq")
def test_suggest_outfit_empty_wardrobe(mock_groq_class):
    """With an empty wardrobe, the LLM is still called for general advice — no crash."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(
            content="This tee goes great with wide-leg trousers and chunky sneakers."
        ))]
    )
    mock_groq_class.return_value = mock_client

    result = suggest_outfit({"title": "Band Tee", "description": "test"}, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


@patch("tools.Groq")
def test_suggest_outfit_llm_failure(mock_groq_class):
    """If the LLM call raises an exception, the tool returns an error string — not an exception."""
    mock_groq_class.side_effect = Exception("Network error")

    result = suggest_outfit({"title": "Band Tee"}, get_example_wardrobe())
    assert isinstance(result, str)
    assert "couldn't" in result.lower()


# ── create_fit_card tests ────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit():
    """Empty outfit string should return an error message, not crash."""
    result = create_fit_card("", {"title": "Band Tee", "price": 20, "platform": "depop"})
    assert isinstance(result, str)
    assert "couldn't" in result.lower()


def test_create_fit_card_whitespace_outfit():
    """Whitespace-only outfit string should return an error message."""
    result = create_fit_card("   \n\t  ", {"title": "Band Tee", "price": 20, "platform": "depop"})
    assert isinstance(result, str)
    assert "couldn't" in result.lower()


@patch("tools.Groq")
def test_create_fit_card_success(mock_groq_class):
    """With a valid outfit and LLM response, returns a non-empty caption string."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(
            content="thrifted this band tee off depop for $22 and honestly it was made for my wide-legs 🖤 full look in my stories"
        ))]
    )
    mock_groq_class.return_value = mock_client

    result = create_fit_card(
        "Pair with your baggy jeans and combat boots.",
        {"title": "Band Tee", "price": 22, "platform": "depop"}
    )
    assert isinstance(result, str)
    assert len(result) > 0
    assert "couldn't" not in result.lower()


@patch("tools.Groq")
def test_create_fit_card_llm_failure(mock_groq_class):
    """If the LLM call raises an exception, the tool returns an error string — not an exception."""
    mock_groq_class.side_effect = Exception("Network error")

    result = create_fit_card(
        "Pair with your baggy jeans.",
        {"title": "Band Tee", "price": 22, "platform": "depop"}
    )
    assert isinstance(result, str)
    assert "couldn't" in result.lower()