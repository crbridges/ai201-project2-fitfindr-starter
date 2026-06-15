# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Looks through the listings.json data and finds items that match what the user typed. Filters out stuff over the price limit and wrong size, then ranks whatever's left by how well the keywords match.

**Input parameters:**
- `description` (str): what they're looking for, like "vintage graphic tee"
- `size` (str): size like "M". some listings are weird like "S/M" so just check if it's in there. can be None
- `max_price` (float): price cap. can be None if they don't care

**What it returns:**
A list of listing dicts, best match first. Each one has id, title, description, category, style_tags, size, condition, price, colors, brand, platform. Empty list if nothing matches.

**What happens if it fails or returns nothing:**
Just returns an empty list, doesn't crash. The agent checks for that and tells the user nothing was found + to try different keywords/price, then stops (doesn't keep going to the next tool).

---
### Tool 2: suggest_outfit

**What it does:**
Takes the item we found and the user's closet and asks the LLM to put together an outfit or two using that item plus stuff they already own.

**Input parameters:**
- `new_item` (dict): the listing we picked from search
- `wardrobe` (dict): the user's wardrobe, has an "items" list. could be empty

**What it returns:**
A string with outfit ideas. If they have a wardrobe it names actual pieces, if it's empty it just gives general advice for the item.

**What happens if it fails or returns nothing:**
If the wardrobe is empty it gives general styling tips instead of crashing. If the LLM call breaks I'll catch it and return a basic fallback string so the app keeps working.

---
### Tool 3: create_fit_card

**What it does:**
Makes a short caption for the outfit, like something you'd actually post on instagram. Uses a higher temperature so it's different each time.

**Input parameters:**
- `outfit` (str): the outfit text from suggest_outfit
- `new_item` (dict): the item, so it can mention the name/price/platform

**What it returns:**
A short 2-4 sentence caption. Casual, mentions the item name, price and platform.

**What happens if it fails or returns nothing:**
If the outfit string is empty it returns an error message instead of trying to make a card. If the LLM errors out it returns a fallback caption.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**

1. Parse the query with the LLM — send the raw text and ask it to return JSON with `description`, `size`, and `max_price`. Save that in `session["parsed"]`. If the JSON comes back broken, fall back to using the whole query as the description with size/max_price = None so search still runs, just unfiltered.
2. Call `search_listings` with those. Look at what comes back:
   - if the list is empty → set `session["error"]` to a "nothing found, try X" message and stop right here. Don't call the other two tools.
   - if there are results → grab the first one (best match), save it as `session["selected_item"]`, keep going.
3. Call `suggest_outfit(selected_item, wardrobe)`. Save the string in `session["outfit_suggestion"]`.
4. Call `create_fit_card(outfit_suggestion, selected_item)`. Save it in `session["fit_card"]`.
5. Return the session.

---

## State Management

**How does information from one tool get passed to the next?**

Everything lives in one `session` dict that gets made at the start of the run and passed down through the loop. Each tool's result gets saved into it, and the next step reads from it instead of asking the user again.

What's in it:
- `query` — the original text the user typed
- `parsed` — the description/size/max_price the LLM pulled out
- `search_results` — the list from search_listings
- `selected_item` — the top result, this is what gets passed into suggest_outfit and create_fit_card
- `wardrobe` — the user's closet
- `outfit_suggestion` — the string from suggest_outfit, gets passed into create_fit_card
- `fit_card` — the final caption
- `error` — set if something went empty and the run stopped early, otherwise None

So the item found in search flows into suggest_outfit through `selected_item`, and that outfit flows into create_fit_card through `outfit_suggestion`. At the end the app reads the keys off the session to fill the three panels.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Returns an empty list. The loop catches it, sets `session["error"]` to a message telling the user nothing matched and to try broader keywords / a higher price / no size, and stops before the other tools. |
| suggest_outfit | Wardrobe is empty | Skips naming pieces and asks the LLM for general styling advice on the item instead. If the LLM call itself errors, it's caught and returns a basic fallback string. |
| create_fit_card | Outfit input is missing or incomplete | If the outfit string is empty/whitespace it returns an error message instead of calling the LLM. If the LLM call errors, returns a simple fallback caption. |

---

## Architecture

```
User query
    │
    ▼
Planning Loop ───────────────────────────────────────────┐
    │                                                    │
    ├─► LLM parse → Session: parsed =                    |
    |      {description, size, max_price}                |
    │                                                    │
    ├─► search_listings(description, size, max_price)    │
    │       │ results=[]                                 │
    │       ├──► [ERROR] "No listings found..." → return │
    │       │                                            │
    │       │ results=[item, ...]                        │
    │       ▼                                            │
    │   Session: selected_item = results[0]              │
    │       │                                            │
    ├─► suggest_outfit(selected_item, wardrobe)          │
    │       │                                            │
    │   Session: outfit_suggestion = "..."               │
    │       │                                            │
    └─► create_fit_card(outfit_suggestion, selected_item)│
            │                                            │
        Session: fit_card = "..."                        │
            │                                            └─ error path returns here
            ▼
        Return session
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
I'll use Claude Code. For each tool I'll point it at that tool's block in this planning.md and the stub in tools.py, and have it implement one tool at a time. After each one I'll print the results in the console to eyeball them, then write some hardcoded tests in tests/test_tools.py to check it's accurate — at least the happy path and the failure mode for each tool (empty search results, empty wardrobe, empty outfit string). Won't move on until the prints look right and the tests pass.

**Milestone 4 — Planning loop and state management:**
Again Claude Code, giving it the Planning Loop, State Management, and Architecture diagram sections from this file plus agent.py. I'll have it implement run_agent() following those steps. To verify, I'll print the session dict in the console after a run and check the values got passed through, and run the no-results query to confirm it sets the error and stops instead of calling the other tools.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "need a 90s track jacket, size M, nothing over $50 — I usually wear baggy jeans and chunky sneakers"

**Step 1:**
LLM parses the query → `{description: "90s track jacket", size: "M", max_price: 50.0}`, saved in `session["parsed"]`.

**Step 2:**
Calls `search_listings("90s track jacket", "M", 50.0)`. Returns matches with the Champion 90s track jacket on top (lst_004, $45, size M, poshmark). It's not empty, so `session["selected_item"]` = that listing and we keep going.

**Step 3:**
Calls `suggest_outfit(selected_item, wardrobe)`. Wardrobe isn't empty so the LLM builds an outfit naming real pieces — e.g. the track jacket over the white ribbed tank, baggy straight-leg jeans, chunky white sneakers. Saved in `session["outfit_suggestion"]`.

**Step 4:**
Calls `create_fit_card(outfit_suggestion, selected_item)`. Returns a short caption mentioning the jacket, the $45 price and poshmark. Saved in `session["fit_card"]`.

**Final output to user:**
The three panels fill in — the listing found (Champion 90s track jacket, $45, poshmark), the outfit idea, and the fit card caption.
