"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    # Build the search keywords from the description
    keywords = [w.lower().strip() for w in description.split() if w.strip()]
    if not keywords:
        return []

    all_listings = load_listings()
    scored = []

    for listing in all_listings:
        # ── Price filter ────────────────────────────────────────────────
        if max_price is not None and listing.get("price") is not None:
            if listing["price"] > max_price:
                continue

        # ── Size filter (case-insensitive, flexible match) ──────────────
        if size is not None:
            item_size = listing.get("size", "")
            size_lower = size.lower().strip()
            item_size_lower = item_size.lower().strip()
            # Flexible match: "M" matches "S/M", "M/L", "One Size", etc.
            # Exact match OR size is contained within item_size OR vice versa
            if not (
                size_lower == item_size_lower
                or size_lower in item_size_lower
                or item_size_lower in size_lower
            ):
                continue

        # ── Relevance scoring: keyword overlap ──────────────────────────
        searchable_text = " ".join([
            listing.get("title", ""),
            listing.get("description", ""),
            *listing.get("style_tags", []),
        ]).lower()

        score = sum(1 for kw in keywords if kw in searchable_text)
        if score > 0:
            scored.append((score, listing))

    # Sort by score descending; preserve order within same score
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    # ── Build item summary ──────────────────────────────────────────────
    item_summary = (
        f"Item: {new_item.get('title', 'Unknown')}\n"
        f"Description: {new_item.get('description', '')}\n"
        f"Category: {new_item.get('category', '')}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Price: ${new_item.get('price', 0):.2f} on {new_item.get('platform', 'N/A')}\n"
        f"Condition: {new_item.get('condition', '')}"
    )

    if wardrobe.get("items"):
        wardrobe_lines = []
        for w_item in wardrobe["items"]:
            notes = f" ({w_item.get('notes', '')})" if w_item.get("notes") else ""
            wardrobe_lines.append(
                f"- {w_item['name']} (category: {w_item['category']}, "
                f"colors: {', '.join(w_item.get('colors', []))}, "
                f"tags: {', '.join(w_item.get('style_tags', []))}){notes}"
            )
        wardrobe_text = "\n".join(wardrobe_lines)
        prompt = (
            f"You are a fashion stylist helping a user style a new thrifted item.\n\n"
            f"{item_summary}\n\n"
            f"The user's existing wardrobe:\n{wardrobe_text}\n\n"
            f"Suggest 1–2 specific outfit combinations using the new item above "
            f"and named pieces from the user's wardrobe. "
            f"Name the specific wardrobe pieces in your suggestion. "
            f"Keep it to 2–5 sentences and sound natural."
        )
    else:
        # Empty wardrobe — give general styling advice
        prompt = (
            f"You are a fashion stylist. A user is considering buying this item:\n\n"
            f"{item_summary}\n\n"
            f"The user hasn't added any items to their wardrobe yet. "
            f"Give 1–2 sentences of general styling advice: "
            f"what kinds of pieces pair well with this item, what vibe it suits, "
            f"and how to style it without referencing specific named pieces."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Couldn't generate an outfit suggestion right now — try again in a moment."


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Couldn't create a fit card — missing outfit data."

    item_name = new_item.get("title", "this item")
    item_price = new_item.get("price", 0)
    platform = new_item.get("platform", "the app")

    prompt = (
        f"Write a short, casual Instagram/TikTok-style caption (2–4 sentences) "
        f"for this OOTD post. It should feel like a real person posting, not a product "
        f"description. Mention the item name ('{item_name}'), price (${item_price:.2f}), "
        f"and platform ('{platform}') naturally — once each. "
        f"Describe the outfit vibe in specific terms. "
        f"Make it sound different each time.\n\n"
        f"Outfit suggestion: {outfit}\n"
        f"New item: {item_name} — ${item_price:.2f} on {platform}"
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Couldn't generate a fit card right now — try again in a moment."
