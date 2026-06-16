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

import json

from tools import search_listings, suggest_outfit, create_fit_card, _get_groq_client


# ── query parsing ─────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Use the LLM to pull structured search params out of the free-text query.

    Returns a dict with keys: description (str), size (str|None), max_price (float|None).
    If the LLM call or JSON parse fails, fall back to using the whole query as
    the description with no filters so search still runs.
    """
    prompt = (
        "Extract search parameters from this thrift-shopping request. "
        "Return ONLY a JSON object with keys: "
        '"description" (string of the item keywords), '
        '"size" (string like "M" or "8", or null if not mentioned), '
        '"max_price" (number, or null if not mentioned).\n\n'
        f"Request: {query}"
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        return {
            "description": data.get("description") or query,
            "size": data.get("size"),
            "max_price": data.get("max_price"),
        }
    except Exception:
        # Fallback: search on the raw query, unfiltered.
        return {"description": query, "size": None, "max_price": None}


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

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: fresh session.
    session = _new_session(query, wardrobe)
    print(f"\n[PLANNING LOOP] new query: {query!r}")

    # Step 2: parse the query into search params (LLM, with fallback).
    session["parsed"] = _parse_query(query)
    parsed = session["parsed"]
    print(f"[STEP 1: parse]  -> {parsed}")

    # Step 3: search.
    session["search_results"] = search_listings(
        parsed["description"], parsed["size"], parsed["max_price"]
    )
    print(f"[STEP 2: search_listings]  -> {len(session['search_results'])} match(es)")

    # Branch: nothing found → set error and return early, do NOT continue.
    if not session["search_results"]:
        bits = [f"'{parsed['description']}'"]
        if parsed["size"]:
            bits.append(f"size {parsed['size']}")
        if parsed["max_price"] is not None:
            bits.append(f"under ${parsed['max_price']}")
        session["error"] = (
            f"No listings matched {', '.join(bits)}. Try broader keywords, "
            "a higher price, or dropping the size filter."
        )
        print("[BRANCH] empty results -> setting error, STOPPING "
              "(suggest_outfit / create_fit_card are NOT called)")
        return session

    # Step 4: pick the top result.
    session["selected_item"] = session["search_results"][0]
    print(f"[STATE] selected_item = {session['selected_item']['title']!r}")

    # Step 5: suggest an outfit from the selected item + wardrobe.
    print("[STEP 3: suggest_outfit]  <- passing selected_item + wardrobe")
    session["outfit_suggestion"] = suggest_outfit(
        session["selected_item"], session["wardrobe"]
    )
    print(f"[STATE] outfit_suggestion stored ({len(session['outfit_suggestion'])} chars)")

    # Step 6: turn it into a shareable fit card.
    print("[STEP 4: create_fit_card]  <- passing outfit_suggestion + selected_item")
    session["fit_card"] = create_fit_card(
        session["outfit_suggestion"], session["selected_item"]
    )
    print("[STATE] fit_card stored -> done\n")

    # Step 7: done.
    return session


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
