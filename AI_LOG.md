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