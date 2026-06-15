# FitFindr 🛍️

An agent that finds secondhand clothing listings, builds an outfit around a find using your wardrobe, and writes a shareable caption for it. Built on Groq's `llama-3.3-70b-versatile`.

## Setup

```bash
pip install -r requirements.txt
```

Add your Groq key to a `.env` file in the repo root (free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## Run

```bash
python app.py
```
Open the URL it prints (usually http://localhost:7860). Pick the example or empty wardrobe, type what you're looking for, and hit "Find it".

Run the tests with:
```bash
pytest tests/
```

## Tool Inventory

### `search_listings(description, size, max_price)`
- **Inputs:** `description` (str) — keywords like "vintage graphic tee"; `size` (str | None) — e.g. "M", matched case-insensitively as a substring so "M" matches "S/M", None skips the filter; `max_price` (float | None) — inclusive price cap, None skips the filter.
- **Returns:** `list[dict]` of matching listings sorted best-match-first. Each dict has `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Empty list if nothing matches.
- **Purpose:** searches the 40-item mock dataset. Pure Python (no LLM), so it's deterministic and unit-tested.

### `suggest_outfit(new_item, wardrobe)`
- **Inputs:** `new_item` (dict) — a listing from `search_listings`; `wardrobe` (dict) — has an `"items"` list of wardrobe pieces, may be empty.
- **Returns:** `str` of outfit ideas. Names real pieces when the wardrobe has items; gives general advice when it's empty.
- **Purpose:** asks the LLM to build 1–2 outfits around the found item.

### `create_fit_card(outfit, new_item)`
- **Inputs:** `outfit` (str) — the suggestion from `suggest_outfit`; `new_item` (dict) — the listing, for the name/price/platform.
- **Returns:** `str` — a short 2–4 sentence social caption. Runs at high temperature so it varies between runs.
- **Purpose:** turns the outfit into something you'd actually post.

## How the Planning Loop Works

`run_agent(query, wardrobe)` in [agent.py](agent.py) runs the tools in order but branches on what comes back:

1. **Parse** the query with the LLM into `{description, size, max_price}`. If the JSON is bad, fall back to using the whole query as the description with no filters.
2. **Search** with those params. **This is the decision point:**
   - if `search_results` is empty → set `session["error"]` and **return early**. The outfit and fit-card tools are never called.
   - if there are results → save `results[0]` as `selected_item` and continue.
3. **Suggest outfit** from `selected_item` + wardrobe.
4. **Create fit card** from the outfit + item.

So the agent doesn't run all three tools no matter what — an empty search stops it and explains why, instead of feeding empty input into the next tool.

## State Management

Everything for one run lives in a single `session` dict created at the start and passed down the loop. Each tool's result is stored in it and the next step reads from it:

- `query` → original text
- `parsed` → the LLM-extracted description/size/max_price
- `search_results` → list from `search_listings`
- `selected_item` → `results[0]`, passed into both `suggest_outfit` and `create_fit_card`
- `outfit_suggestion` → string from `suggest_outfit`, passed into `create_fit_card`
- `fit_card` → final caption
- `error` → set if the run stopped early, otherwise None

The item found in search flows into the outfit step through `selected_item` and the outfit flows into the caption through `outfit_suggestion` — the user never re-enters anything. At the end the app reads the keys off the session to fill the three panels.

## Error Handling

| Tool | Failure mode | What happens |
|------|-------------|--------------|
| `search_listings` | no matches | returns `[]`; the loop sets `session["error"]` and stops before the other tools |
| `suggest_outfit` | empty wardrobe | gives general styling advice instead of naming pieces |
| `suggest_outfit` | LLM call fails | caught, returns a basic fallback string so the loop continues |
| `create_fit_card` | empty/whitespace outfit | returns an error string instead of calling the LLM |
| `create_fit_card` | LLM call fails | caught, returns a simple fallback caption |

**Concrete example from testing:** running `search_listings("designer ballgown", "XXS", 5.0)` returns `[]`. The agent then sets `session["error"]` to *"No listings matched 'designer ballgown', size XXS, under $5. Try broader keywords, a higher price, or dropping the size filter."* and leaves `selected_item`, `outfit_suggestion`, and `fit_card` all `None` — verified in `tests/` and the `agent.py` CLI run.

## Spec Reflection

**One way the spec helped:** the pre-written stub docstrings in `tools.py` (Args, Returns, failure mode, TODO steps) made each tool's interface unambiguous before any code — `search_listings` knowing to match size as a substring came straight from the stub note that "M" should match "S/M".

**One way it diverged:** the scaffold's parse step (step 2) suggested regex/string-splitting as options, but free-text input has no fixed format, so I added an LLM parse step with its own `_parse_query` helper and JSON fallback instead. That's an extra LLM call the original simple design didn't assume, but it handles phrasing like "nothing over $50" without a brittle regex.

## AI Usage

I used Claude Code throughout, directing it with the specific sections of my `planning.md`.

1. **`search_listings` implementation.** I gave it the Tool 1 spec block (inputs, return value, failure mode) and told it to use `load_listings()` from the data loader. It produced a keyword-overlap scorer. I reviewed it against the spec, confirmed it filtered on all three params and returned `[]` (not an exception) on no match, then ran it against 4 queries before trusting it.

2. **Query parsing approach.** Claude initially proposed regex/heuristic parsing for the query. I pushed back — input is unstructured, so I directed it to use the LLM to return JSON instead, with a fallback to the raw query if parsing breaks. I overrode the regex version.

