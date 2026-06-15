# FitFindr — AI Wardrobe Styling Agent

FitFindr is a multi-tool AI agent that helps users find secondhand clothing pieces and figure out how to wear them. Given a natural language query ("vintage graphic tee under $30, size M"), it searches a mock listings dataset, evaluates fit against the user's existing wardrobe, and generates a shareable outfit caption — all orchestrated through a sequential planning loop with explicit error handling at every step.

---

## Project Structure

```
ai201-project2-fitfindr-starter/
├── agent.py              # Planning loop (run_agent) and query parser
├── app.py                # Gradio web interface (handle_query)
├── tools.py              # Three tool implementations
├── utils/
│   └── data_loader.py    # load_listings, get_example_wardrobe, get_empty_wardrobe
├── data/
│   ├── listings.json     # 40 mock secondhand listings
│   └── wardrobe_schema.json  # Wardrobe schema + example wardrobe
├── tests/
│   └── test_tools.py     # 12 pytest tests covering all failure modes
├── planning.md           # Full agent specification
└── requirements.txt
```

---

## Tool Inventory

### Tool 1: `search_listings`

**File:** `tools.py`

**What it does:** Filters the mock listings dataset by description keywords, optional size, and optional max price — then scores remaining listings by keyword relevance and returns them sorted highest-first.

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `description` | `str` | Free-text search terms (e.g., `"vintage graphic tee"`). Matched case-insensitively against `title`, `description`, and `style_tags` fields. |
| `size` | `str \| None` | Size to filter by. Case-insensitive, flexible — `"M"` matches `"S/M"`, `"One Size"`, etc. `None` skips size filtering. |
| `max_price` | `float \| None` | Maximum price in dollars (inclusive). `None` skips price filtering. |

**Output:** A list of matching listing dicts sorted by relevance score (best match first), e.g. `[{"id": "lst_006", "title": "Graphic Tee — 2003 Tour Bootleg Style", "price": 24.0, ...}, ...]`. Returns `[]` (no exception) when nothing matches.

**Purpose:** Acts as the entry point — finds candidate items before the agent commits to styling work.

---

### Tool 2: `suggest_outfit`

**File:** `tools.py`

**What it does:** Given a selected listing and the user's wardrobe, generates 1–2 specific outfit combinations using named pieces from the user's closet. Falls back to general styling advice if the wardrobe is empty.

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `new_item` | `dict` | A listing dict for the item the user is considering buying. |
| `wardrobe` | `dict` | A wardrobe dict with an `'items'` key containing a list of wardrobe item dicts. May be empty. |

**Output:** A non-empty string (2–5 sentences) with concrete outfit suggestions naming specific wardrobe pieces, e.g. *"Pair this with your Baggy straight-leg jeans, dark wash and combat boots for a classic grunge look."* If the wardrobe is empty, general styling advice is returned instead.

**Purpose:** Bridge between "found an item" and "know how to wear it" — grounds the new piece in pieces the user already owns.

---

### Tool 3: `create_fit_card`

**File:** `tools.py`

**What it does:** Takes an outfit suggestion and the new item, then generates a short, shareable Instagram/TikTok-style caption via Groq LLM.

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit()`. |
| `new_item` | `dict` | The listing dict for the thrifted item. |

**Output:** A 2–4 sentence caption string that mentions item name, price, and platform naturally and sounds like a real OOTD post. Example: *"thrifted this faded band tee off depop for $22 and honestly it was made for my wide-legs 🖤 full look in my stories"*

**Purpose:** Turns the agent's output into something the user can actually share — the final deliverable of a successful interaction.

---

## Planning Loop

The planning loop is a **sequential pipeline** — it always runs in the same order (search → suggest → fit_card), with exactly one early-exit branch when `search_listings` finds nothing.

```
User query
    │
    ▼
_parse_query()  ── extracts description, size, max_price
    │
    ▼
search_listings(description, size, max_price)
    │
    ├──► results == []  ──► session["error"] = "No listings found..."
    │                    └──► RETURN session early (skip steps 5 & 6)
    │
    ▼
session["selected_item"] = results[0]
    │
    ▼
suggest_outfit(selected_item, wardrobe)  ──► session["outfit_suggestion"]
    │
    ▼
create_fit_card(outfit_suggestion, selected_item)  ──► session["fit_card"]
    │
    ▼
RETURN session
```

**Query parsing** uses lightweight regex — no LLM call needed. It extracts:
- `description`: everything except size/price modifiers
- `size`: value after the word "size" (case-insensitive)
- `max_price`: last dollar amount after `$`

The agent is **not a router** — it doesn't decide which tool to call based on intermediate results. All three tools run in sequence when search succeeds. The only conditional is the early exit on empty search results.

---

## State Management

All state lives in a single `session` dict that is built up incrementally by each step:

| Field | Set by | Read by |
|---|---|---|
| `query` | `_new_session()` | — |
| `parsed` | `_parse_query()` | `search_listings` |
| `search_results` | `search_listings` | — |
| `selected_item` | `search_results[0]` | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | `_new_session()` | `suggest_outfit` |
| `outfit_suggestion` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `create_fit_card` | — |
| `error` | Any step on failure | Agent framework |

Each step reads only the fields it needs and writes only its own output. The `error` field, if set, short-circuits the remaining steps. No class, no global variables — just a dict passed between functions.

---

## Error Handling

| Tool | Failure mode | What the user sees |
|---|---|---|
| `search_listings` | No results match the query | *"No listings found for that search — try broadening your size or increasing your budget."* `fit_card` and `outfit_suggestion` stay `None`. |
| `suggest_outfit` | Wardrobe is empty (`wardrobe["items"] == []`) | LLM is still called with a general-styling prompt; no crash, no empty string returned. |
| `suggest_outfit` | LLM API call fails | *"Couldn't generate an outfit suggestion right now — try again in a moment."* |
| `create_fit_card` | `outfit` input is empty/whitespace | *"Couldn't create a fit card — missing outfit data."* |
| `create_fit_card` | LLM API call fails | *"Couldn't generate a fit card right now — try again in a moment."* |

**Concrete test example — empty wardrobe:**
```python
from tools import suggest_outfit
from utils.data_loader import get_empty_wardrobe

suggest_outfit({"title": "Y2K Baby Tee"}, get_empty_wardrobe())
# Returns: "This adorable Y2K baby tee is perfect for creating a playful,
# nostalgic look and pairs well with high-waisted bottoms, flowy skirts,
# or distressed denim for a laid-back, vintage-inspired vibe..."
# (general advice, no crash, no empty string)
```

**Concrete test example — empty search results:**
```python
from agent import run_agent
from utils.data_loader import get_example_wardrobe

session = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())
print(session["error"])
# → "No listings found for that search — try broadening your size or increasing your budget."
print(session["fit_card"])
# → None  (suggest_outfit was never called)
```

---

## AI Usage

FitFindr was built with significant AI assistance. Here are two specific instances:

### Instance 1: Tool implementations (`tools.py`)

**What I gave the AI tool:**
- The Tool 1, 2, and 3 blocks from `planning.md` — each with: what the tool does, exact input parameters (name, type, meaning), what it returns, and the specific failure mode to handle
- The existing `tools.py` stubs showing function signatures and TODO comments
- The `data/listings.json` and `wardrobe_schema.json` schemas for context
- `utils/data_loader.py` — specifically instructed to use `load_listings()` rather than re-implementing file loading

**What it produced:**
- `search_listings` with keyword-overlap scoring: split description into tokens, check each against title + description + style_tags, filter by price and flexible size match, sort by score
- `suggest_outfit` with a branching prompt: if wardrobe non-empty, include all wardrobe items in prompt and ask for named-piece suggestions; if empty, give general styling advice
- `create_fit_card` with temperature=0.8 for varied output and a guard against empty outfit input

**What I changed:** The AI put `client = _get_groq_client()` **outside** the `try` block in both LLM tools. I moved it inside the `try` so that a `Groq(api_key=...)` exception (not just the API call itself) would be caught and returned as a string rather than propagating as an unhandled exception.

### Instance 2: Planning loop (`agent.py`)

**What I gave the AI tool:**
- The full Planning Loop pseudocode section from `planning.md`
- The State Management table (which field is set by which step, read by which step)
- The Architecture ASCII diagram
- The `run_agent()` TODO steps in `agent.py`

**What it produced:**
- The sequential pipeline structure (search → suggest → fit_card) matching the spec exactly
- Early exit when `search_results == []`
- Session dict construction with all required fields

**What I changed:** The AI-generated `run_agent()` called `suggest_outfit` and `create_fit_card` unconditionally after search succeeded, but didn't check whether `suggest_outfit`'s return value was an error-indicator string. I added the error-check logic (`if "couldn't" in suggestion.lower()`) before passing the outfit to `create_fit_card`, matching the exact branching described in the Planning Loop section.

---

## Running the App

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Groq API key
echo "GROQ_API_KEY=your_key_here" > .env

# Run the web interface
python app.py
```

Then open the URL printed in your terminal (check for `http://127.0.0.1:7860` or similar).

**Example queries to try:**
- `vintage graphic tee under $30` — happy path, all three panels fill
- `90s track jacket size M` — happy path
- `designer ballgown size XXS under $5` — no-results path, error in first panel
- `black combat boots size 8` — happy path with empty wardrobe option

**Run tests:**
```bash
pytest tests/ -v
```
All 12 tests pass, covering every failure mode across all three tools.