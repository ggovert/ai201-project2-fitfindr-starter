# FitFindr — planning.md

---

## Tools

List every tool your agent will use. Each tool is a standalone function that can be called and tested independently before being wired into the agent loop.

### Tool 1: search_listings

**What it does:**
Filters the mock listings dataset by description keywords, optional size, and optional max price — then scores remaining listings by keyword relevance and returns them sorted highest-first.

**Input parameters:**
- `description` (str): Free-text search terms (e.g., "vintage graphic tee"). Matched case-insensitively against `title`, `description`, and `style_tags` fields of each listing.
- `size` (str | None): Size to filter by, or None to skip size filtering. Matching is case-insensitive and flexible — "M" matches "S/M", "M/L", "One Size", etc.
- `max_price` (float | None): Maximum price in dollars (inclusive), or None to skip price filtering.

**What it returns:**
A list of matching listing dicts sorted by relevance score (best match first), each containing:
- `id` (str): Unique listing identifier (e.g., "lst_006")
- `title` (str): Short listing title
- `description` (str): Full listing description
- `category` (str): One of tops, bottoms, outerwear, shoes, accessories
- `style_tags` (list[str]): Style descriptors (e.g., ["grunge", "vintage", "band tee"])
- `size` (str): Size string as stored in the data
- `condition` (str): excellent, good, or fair
- `price` (float): Price in dollars
- `colors` (list[str]): List of colors
- `brand` (str | None): Brand name or null
- `platform` (str): depop, thredUp, or poshmark

**What happens if it fails or returns nothing:**
Returns an empty list `[]`. The planning loop detects `results == []`, sets `session["error"] = "No listings found for that search — try broadening your size or increasing your budget."`, and returns the session immediately without calling further tools.

---

### Tool 2: suggest_outfit

**What it does:**
Given a selected listing and the user's wardrobe, generates 1–2 specific outfit combinations using named pieces from the user's closet paired with the new item. If the wardrobe is empty, returns generic styling advice for the new item instead.

**Input parameters:**
- `new_item` (dict): A listing dict for the item the user is considering buying.
- `wardrobe` (dict): A wardrobe dict with an `'items'` key containing a list of wardrobe item dicts. Each item has: `id` (str), `name` (str), `category` (str), `colors` (list[str]), `style_tags` (list[str]), `notes` (str | None).

**What it returns:**
A non-empty string (2–5 sentences) with concrete outfit suggestions. If the wardrobe is non-empty, the string names specific wardrobe pieces (e.g., "Pair this with your Baggy straight-leg jeans, dark wash…"). If the wardrobe is empty, the string offers general styling direction without referencing named pieces (e.g., "A tee like this goes great with wide-leg trousers and chunky sneakers…").

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the LLM is still called with a general-styling prompt so a helpful string is always returned — no error is raised. If the LLM call itself fails (network error, API error), the tool returns the string: "Couldn't generate an outfit suggestion right now — try again in a moment."

---

### Tool 3: create_fit_card

**What it does:**
Takes an outfit suggestion string and the new item, then uses an LLM to generate a short, shareable social-media caption (2–4 sentences) that feels casual and authentic.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit()`.
- `new_item` (dict): The listing dict for the thrifted item.

**What it returns:**
A 2–4 sentence Instagram/TikTok-style caption string that:
- Mentions the item name, price, and platform naturally (once each)
- Captures the outfit vibe in specific terms
- Sounds casual and authentic, not like a product description
- Varies in phrasing for different inputs (LLM temperature > 0.5)

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, returns the string: "Couldn't create a fit card — missing outfit data." If the LLM call fails, returns: "Couldn't generate a fit card right now — try again in a moment."

---

### Additional Tools (if any)
No additional tools beyond the three required.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop is a sequential pipeline — it always runs in the same order: search → suggest → fit_card. It is not a random-access router; the three tools always execute in sequence, and the loop can terminate early at any step on error.

**Specific logic (pseudocode):**

```
session = {"query": user_query, "results": None, "selected_item": None,
           "outfit_suggestion": None, "fit_card": None, "error": None}

1. Parse user query → extract description, size (optional), max_price (optional).
   If parse fails, set error = "I didn't catch that — try describing what you're
   looking for along with a size and max budget." and return session.

2. Call search_listings(description, size, max_price).
   If results == []:
       session["error"] = "No listings found for that search — try broadening
       your size or increasing your budget."
       return session
   session["results"] = results
   session["selected_item"] = results[0]  # top relevance match

3. Call suggest_outfit(new_item=session["selected_item"], wardrobe=user_wardrobe).
   If suggest_outfit returns an error-indicator string (contains "Couldn't"):
       session["outfit_suggestion"] = "Style tip: " + the returned string
   Else:
       session["outfit_suggestion"] = returned string

4. Call create_fit_card(outfit=session["outfit_suggestion"],
                        new_item=session["selected_item"]).
   If create_fit_card returns an error-indicator string:
       session["fit_card"] = "Fit card unavailable."
   Else:
       session["fit_card"] = returned string

5. Return session (all fields populated, error may be None or set)
```

**When is the loop done?**
When Step 5 returns — the session always contains either a complete result or an explicit error message. There is no retry loop, no conditional branching on tool output beyond the early-exit on empty search results.

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in a single `session` dict that is passed from step to step. No class, no global variables. The session is built up incrementally:

| Field | Set by | Read by |
|---|---|---|
| `query` | Planning loop (user input) | — |
| `results` | Step 2 (`search_listings`) | — |
| `selected_item` | Step 2 (`results[0]`) | Step 3 (`suggest_outfit`) |
| `outfit_suggestion` | Step 3 (`suggest_outfit`) | Step 4 (`create_fit_card`) |
| `fit_card` | Step 4 (`create_fit_card`) | — |
| `error` | Any step on failure | Agent framework |

Each step reads only the fields it needs from the session and writes only its own output field. The `error` field, if set, short-circuits the remaining steps.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query (returns `[]`) | Sets `session["error"] = "No listings found for that search — try broadening your size or increasing your budget."` and returns the session immediately. Does not call suggest_outfit or create_fit_card. |
| search_listings | LLM/API call fails (not applicable — this tool does no LLM call) | N/A — search_listings is a deterministic filter over local data; it cannot fail this way. |
| suggest_outfit | Wardrobe is empty (`wardrobe["items"] == []`) | Calls LLM with a general-styling prompt (no wardrobe pieces named) and returns the advice string normally. No error flag set. |
| suggest_outfit | LLM API call fails (network/timeout/auth error) | Returns `"Couldn't generate an outfit suggestion right now — try again in a moment."` — includes this in `session["outfit_suggestion"]` with a "Style tip:" prefix rather than erroring out. |
| create_fit_card | `outfit` input is empty or whitespace | Returns `"Couldn't create a fit card — missing outfit data."` as the fit_card value. |
| create_fit_card | LLM API call fails | Returns `"Couldn't generate a fit card right now — try again in a moment."` as the fit_card value. |

---

## Architecture

```
User query: "vintage graphic tee, size M, under $30"
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Planning Loop                                                      │
│                                                                     │
│  1. Parse query → extract description="vintage graphic tee",        │
│                      size="M", max_price=30.0                       │
│                                                                     │
│  2. search_listings(description, size="M", max_price=30.0)         │
│         │                                                           │
│         ├──► results == []                                          │
│         │    Session: error = "No listings found..."                │
│         │    └──────────────────────────────────► RETURN session    │
│         │                                                           │
│         │ results = [lst_006, lst_033, lst_002, ...] (sorted)       │
│         ▼                                                           │
│     Session: selected_item = results[0]  (lst_006 — Graphic Tee)    │
│                                                                     │
│  3. suggest_outfit(new_item=selected_item, wardrobe=user_wardrobe)  │
│         │                                                           │
│         ▼                                                           │
│     Session: outfit_suggestion = "Pair this with your baggy         │
│              straight-leg jeans and chunky sneakers..."             │
│                                                                     │
│  4. create_fit_card(outfit=outfit_suggestion, new_item=selected_item│
│         │                                                           │
│         ▼                                                           │
│     Session: fit_card = "thrifted this faded band tee off depop    │
│              for $22 and honestly it was made for my wide-legs 🖤"  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
Final session returned to user
  - fit_card: the caption string
  - outfit_suggestion: the styling advice
  - selected_item: the matched listing
  - results: all matched listings
  - error: None (if successful)
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

I'll use **Claude (claudeaude)** via the CLI to generate each tool implementation. For each tool, I'll provide:
- The specific `### Tool N: <name>` block from this planning.md (description, input params, return value, failure mode)
- The relevant data structures from `data/listings.json` and `data/wardrobe_schema.json` for context
- The existing stub in `tools.py` as a reference for signature and TODO comments
- The helper functions from `utils/data_loader.py` that must be used

**For `search_listings`:** I'll give Claude the Tool 1 block + a sample of 3 listings from `listings.json` to show the data shape. I'll ask it to implement the scoring function using simple keyword overlap (description matched against title + description + style_tags). I'll verify by running 3 test queries:
1. Exact match (vintage graphic tee → should return lst_006)
2. No match (unicorn raincoat → should return [])
3. Price filter only (max_price=20, no size/description → should return multiple)

**For `suggest_outfit`:** I'll give Claude the Tool 2 block + the `example_wardrobe` items and the `empty_wardrobe` schema. I'll ask it to call the Groq LLM with a well-structured prompt that includes both the new item and the wardrobe. I'll verify by calling it twice: once with the example wardrobe (should reference named pieces like "baggy straight-leg jeans") and once with `get_empty_wardrobe()` (should give generic advice without crashing).

**For `create_fit_card`:** I'll give Claude the Tool 3 block + examples of good OOTD captions. I'll ask it to call the Groq LLM with temperature=0.7. I'll verify by calling with two different outfits and confirming the outputs differ in phrasing.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the **Planning Loop**, **State Management**, and **Architecture** sections of planning.md, plus the existing `tools.py` stubs. I'll ask it to implement the planning loop as a function `run_agent(query, wardrobe)` that returns a session dict, wiring the three tools together with the exact conditional branches described in the Planning Loop section. I'll verify by running the full example query from A Complete Interaction and checking that all session fields are populated correctly.

---

## A Complete Interaction (Step by Step)

FitFindr is a multi-tool AI agent that helps users find secondhand clothing pieces and figure out how to wear them. When a user describes what they're looking for (e.g., "vintage graphic tee under $30"), the planning loop triggers `search_listings` to find matching items; if that returns nothing or fails, the agent informs the user and stops. If results are found, `suggest_outfit` evaluates the items against the user's existing wardrobe to build an outfit, and finally `create_fit_card` generates a shareable description of the full look — with each step handling its own failure mode gracefully (empty results, missing wardrobe data, or incomplete outfit input all result in a clear user-facing message rather than a crash).

**Example user query:** "I'm looking for a vintage graphic tee under $30, size M. I mostly wear baggy jeans and chunky sneakers."

**Step 1:** The planning loop parses the query into `description="vintage graphic tee"`, `size="M"`, `max_price=30.0`. It calls `search_listings(description="vintage graphic tee", size="M", max_price=30.0)`. This loads all 40 listings from `listings.json`, filters to those ≤ $30 and matching size M (flexible match — "M" matches "S/M", "One Size", etc.), scores the remaining listings by keyword overlap with "vintage graphic tee" against title, description, and style_tags, drops any with score 0, and sorts descending. The top result is `lst_006`: **{"id": "lst_006", "title": "Graphic Tee — 2003 Tour Bootleg Style", "description": "Vintage-style bootleg tee with faded graphic...", "category": "tops", "style_tags": ["graphic tee", "vintage", "grunge", "streetwear", "band tee"], "size": "L", "condition": "good", "price": 24.00, "colors": ["black"], "brand": null, "platform": "depop"}**. The session stores `selected_item = lst_006`.

**Step 2:** The planning loop calls `suggest_outfit(new_item=lst_006, wardrobe=example_wardrobe)`. The tool formats the new item details and all 10 example wardrobe items into an LLM prompt asking for 1–2 specific outfit combinations. The LLM returns: *"This bootleg tee pairs perfectly with your Baggy straight-leg jeans, dark wash for that classic grunge look. Add your Black combat boots and let the tee hang untucked over the jeans for a relaxed 90s vibe — roll the sleeves once for extra shape."* The session stores `outfit_suggestion` = that string.

**Step 3:** The planning loop calls `create_fit_card(outfit=<suggestion string>, new_item=lst_006)`. The tool sends the outfit suggestion and listing details to the Groq LLM with instructions for a 2–4 sentence Instagram caption that mentions item name, price, and platform naturally. The LLM returns: *"thrifted this faded 2003 tour bootleg tee off depop for $24 and honestly it was made for my baggy dark-wash jeans 🖤 full fit coming to my stories tonight"* The session stores `fit_card` = that string.

**Final output to user:** The agent returns a session dict containing:
- `fit_card`: "thrifted this faded 2003 tour bootleg tee off depop for $24 and honestly it was made for my baggy dark-wash jeans 🖤 full fit coming to my stories tonight"
- `outfit_suggestion`: the styling advice from Step 2
- `selected_item`: the full lst_006 listing dict
- `results`: all matching listings sorted by relevance (lst_006 plus any other graphic tees under $30 that scored > 0)
- `error`: None

The user sees the fit card caption and outfit suggestion, plus a link to the listing.