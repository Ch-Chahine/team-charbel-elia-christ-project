# AI Log — Charbel Chahine (202401056)

**Tool:** Claude (Anthropic), used as a senior teammate — AI Level 2 (Assisted).
**AI's role:** explained concepts, suggested code and tests, reviewed my code and Git steps.
**My role:** I made every design decision, typed all the code myself, and tested each step before committing.

---

## 12 Nov 2026 — Feature branch and api_client setup
- **Asked:** how to plan `search_towns`; how to start a feature branch.
- **Used:** `git checkout -b feature/api-client`; imports, module logger, `TIMEOUT`, `GEOCODING_SEARCH_URL`.
- **My decision:** a module logger (`logging.getLogger(__name__)`) instead of `app.logger`, to avoid a circular import with `app.py`.
- **Tested:** `python -c "import api_client"` printed the logger and URL; opening the base URL alone in the browser returned HTTP 400 `{"error": true, ...}` → parameters required, errors come back as JSON.

## 13 Nov 2026 — `search_towns`
- **Asked:** how to validate input, call the API safely, and reshape the results.
- **My decisions:**
  - `None` = API failed, `[]` = invalid input or no match.
  - Minimum length **2** (the proposal said "non-empty"): Open-Meteo returns nothing for 1 character.
  - Allow-list regex (letters incl. accented and Arabic, space . ' -), following Week 11.
  - Result fields: `id, name, region, district, lat, lon`; `""` default for displayed text, `None` for coordinates.
- **Tested:**
  - `None`, `" J "`, `"<b>"`, 61 characters → `[]` (no API call).
  - `"Jounieh"` → `273140 Jounieh Mount Lebanon`; `"Zzzqqq"` → `[]`.
  - Wi-Fi off → warning logged + `None`; a real slow network → `ConnectTimeoutError (timeout=6)` + `None`.
  - `"Zah"` → 4 towns, one with no region shown as empty (no crash).
- **Lesson:** a caller must check `is None` before looping (my test crashed on `None`), so the route checks it.

## 13 Nov 2026 — `get_town`
- **Asked:** how to look up one town by id and handle "not found".
- **Tested in the browser first:** `get?id=273140` (town returned directly, not in "results"), `id=999999999` ("Location ID not found"), `id=abc` (Int32 error) → id range 1 to 2,147,483,647.
- **My decisions:**
  - `{}` = no such town (bad id, not found, or outside Lebanon), `None` = API failed.
  - Check `country_code == "LB"` so a URL can't show a town outside Lebanon.
- **Tested:** `None`, `"abc"`, `0`, `-5`, `3000000000` → `{}`; `273140` → Jounieh; `999999999` → `{}` with no warning; Paris `2988507` → `{}`; Wi-Fi off → warning + `None`.

## 13 Nov 2026 — `validate_search`, `/search`, `/town/<place_id>`
- **Asked:** how to show user-friendly errors and connect the functions to pages.
- **My decisions:**
  - Two validation layers (Week 11 defense in depth): `api_client` protects the API call; `validators.validate_search` gives the user a message and reuses the same constants.
  - The search page has 4 states: invalid input, API down, no match, towns found (`role="alert"` / `role="status"`).
  - The town page: 404 for `{}`, 503 for `None`.
- **Tested:**
  - `validate_search`: `""`, `" J "`, `"<b>"` → correct messages; `" Jounieh "` → valid, spaces removed.
  - Browser: `/search?q=jounieh` → Jounieh card; `/town/273140` → Jounieh page; `/town/999999999` → 404.

## 14 Nov 2026 — Review and team workflow
- **Asked:** a line-by-line review of all my code for the oral defense; how teammates see and merge each other's branches.
- **Used:** the Git workflow (branches → pull request → review → merge → everyone merges `main`), now in our project plan.

## 14 Nov 2026 — Link search results to town pages
- **Asked:** how to make each search result open its town page.
- **Used:** `url_for('town', place_id=town.id)` inside each card's `<h2>` in `results.html`.
- **Tested:** searched "Zah" → clicked Zahle → `/town/266045` showed Zahle, Bekaa, 33.84675, 35.90203; Tab + Enter also opens the links (keyboard access).

## 14 Nov 2026 — Towns with no region
- **Found:** "Ẓahr Baydar Durrah" (id 11260674) has no `admin1`/`admin2` in Open-Meteo's data, so its card had an empty line.
- **My decision:** show "Lebanon" when the region is missing (`{{ town.region or "Lebanon" }}` in `results.html` and `town.html`). It is always true because we only accept towns with country code LB.
- **Why in the template:** `api_client` keeps returning the real empty value; only the page decides how to display "unknown".
- **Tested:** "Zah" → 4th card shows "Lebanon"; Zahle still shows "Bekaa".

## 14 Nov 2026 — Minimum search length
- **Question I raised:** should 1 character be enough, like on many websites?
- **Checked:** Open-Meteo's documentation says 0–1 characters return nothing, 2 return exact matches only, 3+ fuzzy matches; confirmed in the browser (`name=Z` → no results, `name=Zah` → Zahle…).
- **My decision:** keep the minimum at 2, so users get a clear message instead of a misleading "no towns found". Changing it later is one constant (`MIN_SEARCH_LENGTH`), shared by `api_client.py` and `validators.py`.