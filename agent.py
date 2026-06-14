"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

import re


def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.
    """
    session = _new_session(query, wardrobe)

    # ── Step 2: Parse the query ──────────────────────────────────────────
    # Simple regex-based parser (no LLM needed):
    #   "vintage graphic tee under $30, size M"
    # Extracts: description, optional size (after "size"), optional max_price (after "$")
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # ── Step 3: search_listings ──────────────────────────────────────────
    results = search_listings(
        description=parsed["description"],
        size=parsed.get("size"),
        max_price=parsed.get("max_price"),
    )
    session["search_results"] = results

    if not results:
        session["error"] = (
            "No listings found for that search — try broadening your size "
            "or increasing your budget."
        )
        return session

    # ── Step 4: Select top result ────────────────────────────────────────
    session["selected_item"] = results[0]

    # ── Step 5: suggest_outfit ───────────────────────────────────────────
    suggestion = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=wardrobe,
    )
    session["outfit_suggestion"] = suggestion

    # ── Step 6: create_fit_card ──────────────────────────────────────────
    fit_card = create_fit_card(
        outfit=suggestion,
        new_item=session["selected_item"],
    )
    session["fit_card"] = fit_card

    # ── Step 7: Return session ───────────────────────────────────────────
    return session


def _parse_query(query: str) -> dict:
    """
    Lightweight regex parser for user queries.

    Extracts:
      - description:  everything except size/price modifiers
      - size:         value after "size" (case-insensitive)
      - max_price:    value after "$" as a float

    Examples:
      "vintage graphic tee under $30, size M"
        → {"description": "vintage graphic tee", "size": "M", "max_price": 30.0}
      "90s track jacket in size M" → {"description": "90s track jacket", "size": "M"}
      "black combat boots size 8"  → {"description": "black combat boots", "size": "8"}
    """
    q = query.strip()
    parsed = {"description": q}

    # Extract size: "size M" or ", size M" anywhere in the string
    size_match = re.search(r'(?:,?\s*size\s+)([A-Za-z0-9/]+)', q, re.IGNORECASE)
    if size_match:
        parsed["size"] = size_match.group(1).strip()

    # Extract max_price: "$30" or "$ 30" — take the last such occurrence
    price_matches = re.findall(r'\$\s*(\d+(?:\.\d+)?)', q)
    if price_matches:
        parsed["max_price"] = float(price_matches[-1])

    # Clean up description: remove size and price phrases we extracted
    desc = re.sub(r',?\s*size\s+[A-Za-z0-9/]+', '', q, flags=re.IGNORECASE)
    desc = re.sub(r'\$\s*\d+(?:\.\d+)?', '', desc)
    desc = re.sub(r'under\s+\$?\d+(?:\.\d+)?', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'less than\s+\$?\d+(?:\.\d+)?', '', desc, flags=re.IGNORECASE)
    parsed["description"] = re.sub(r'\s+', ' ', desc).strip()

    return parsed


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
