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

## 14 Nov 2026 — Home page
- **Asked:** how to make the home search box accessible.
- **Used:** a real `<label for="q">`, `role="search"`, a hint linked with `aria-describedby`, and `minlength`/`maxlength`/`required` on the input.
- **My understanding/decision:** the browser checks are only a convenience; the server checks (`validate_search` + `search_towns`) are the real protection (Week 11: never trust the client).
- **Tested:** clicking the label focuses the box; typing "J" is blocked by the browser; typing `/search?q=J` directly in the address bar shows the server's message.

## 14 Nov 2026 — Removing the starter's sample code
- **Asked:** what to delete safely.
- **Used:** removed `_SAMPLE`, `search()`, `get_item()`, the `/item` route and `detail.html`; changed one link in `favorites.html` to `url_for('town', ...)` so it doesn't break (Elia will remove Favorite later).
- **Tested:** `hasattr(api_client, 'get_item')` → False; `/item/1` → 404; home, search and town pages still work. A real network slowdown showed the 503 "service not responding" page; a refresh worked.

## 14 Nov 2026 — First pull request and team workflow
- **Asked:** how teammates see each other's branches and how to merge safely.
- **Done:** turned on branch protection on `main` (PR + 1 approval). Opened PR #2 with a description (what / contract / security / tests). Elia approved and merged it (bd6aeb7).
- **Problem found:** the live site didn't change — Render's Auto-Deploy was off. Did a Manual Deploy → the live site showed real Open-Meteo data.
- **Reviewed Elia's PR #3 (models.py):** checked that `place_id` is an Integer and that the azimuth convention matches Open-Meteo; pointed out that Render's existing tables won't get the new columns (`create_all` doesn't alter tables). Approved and merged it (f559bd6).

## 15 Nov 2026 — Town forecast (`get_town_forecast`)
- **Asked:** how to show a 3-day sunshine forecast on the town page.
- **Tested in the browser first:** the forecast JSON has two parallel lists (`time`, `shortwave_radiation`), 72 values, unit W/m², GMT+2; coordinates are snapped to Open-Meteo's grid; `latitude=999` returns an error JSON.
- **My decisions:** same contract as search — a list on success, `[]` for invalid lat/lon, `None` if the API fails; pair the two lists with `zip`; skip `null` hours instead of inventing a value.
- **Debugging:** fixed two indentation bugs where code ended up inside an `if` after a `return`/`abort` and never ran (`NameError`).
- **Tested:** invalid inputs → `[]`; Jounieh → 72 hours; Wi-Fi off → warning + `None`.

## 15 Nov 2026 — Daily sunshine (`solar.daily_sunshine`) and the town page table
- **Formula:** each hourly value is an average in W/m², so it equals Wh/m² for that hour; daily kWh/m² = sum of the hourly values ÷ 1000 (same idea as "peak sun hours").
- **Tested by hand:** 500 + 600 W/m² → 1.1 kWh/m², peak at 12:00. Jounieh on the page: 3.2 / 2.99 / 2.73 kWh/m² for 15–17 Nov.
- **Page:** a real `<table>` with `<caption>` and `<th scope>`, plus error and empty states. PR #4, merged by Elia.

## 15 Nov 2026 — Tilted-panel forecast (`get_forecast`)
- **Tested in the browser first:** with tilt 30° facing south, 763.8 W/m² at 13:00 vs 539 W/m² on a flat surface (~42% more in November, because the winter sun is low).
- **Validation:** tilt 0–90, azimuth −180..180, past_days 0–7 (same ranges as the proposal).
- **Tested:** 72 hours; `past_days=7` → 240 hours; tilt 120 → `[]`. An accidental offline run → warning + `None` (the logged URL showed `params` encoding commas and slashes).

## 15 Nov 2026 — Winter sun hours (`get_winter_sun_hours`)
- **Tested in the browser first:** the archive API returned 365 days of `shortwave_radiation_sum` in MJ/m², no missing values.
- **Calculated by hand from that data:** monthly peak sun hours (MJ/m² ÷ 3.6) — best June 7.97, worst December 2.46.
- **My decision:** changed the fallback from the proposal's 3.0 to 2.5, because real December data (2.46) showed 3.0 would undersize systems by about 20% when the API is down. The function always returns a number (the planner needs one), and failures are logged.
- **Tested:** Jounieh → 2.46 (matches my manual calculation); invalid input → 2.5. The first run hit a real connect timeout → logged + 2.5; a direct request seconds later took 0.4 s, so it was a network hiccup.

## 15 Nov 2026 — Caching
- **Asked:** how to avoid calling Open-Meteo again for the same question.
- **Used:** an in-memory dict with expiry times (`_cache_get` / `_cache_set`): towns and winter sun hours 24 h, forecasts 30 min, maximum 500 entries.
- **My rules:** never cache failures or the fallback value; an empty result (`[]`) is a valid answer and is cached.
- **Bugs found during AI review and fixed:** `_cache_set` was inside the `for` loop (saved once per town, never saved `[]`); `get_town` returned before saving to the cache; a loop variable named `time` hid the `time` module (renamed to `when`).
- **Tested:** `get_town` first call 1.2–5.8 s (slow network), second call 0.0 s; "Jounieh" then "JOUNIEH" share one cache entry.

## 15 Nov 2026 — Planner maths (`sizing.py`)
- **Asked:** how to turn the proposal's formula table into code, step by step, testing each function alone.
- **Used:** `load_summary`, `panel_power`, `panels_needed`, `inverter_size`, `battery_size`, `architecture`, `suggest_system`; every constant named and commented.
- **My decision (change from the proposal):** panels are sized for **day + night** energy: `kWp = (E + E_night) ÷ (PSH × 0.8)`, because the panels must also recharge the battery for the night. The worked example goes from 8 to 11 panels.
- **Other decisions:** `inverter_size` returns `None` above 12 kW (never suggest an undersized inverter); `load_summary` trusts its input because the appliance form validates it.
- **Tested (each checked by hand):** worked example → 10 / 4 / 3.5 kW; 4.17 kWp → 8 panels, 4.4 kWp, 20.8 m² (= proposal); battery (4 kWh, 1 day) → 10 kWh, 2 modules (= proposal); inverter 3.5 kW → 5 kW, 10 kW → None. Full chain with Jounieh's real winter value (2.46), off-grid → 13 panels, 7.15 kWp, 33.8 m², 5 kW, 10 kWh (vs 11 panels with 3.0).

## 16 Nov 2026 — Review of Christ's appliances PR
- **Found:** his templates had a second `<main>` inside the one from `base.html`.
- **My decision:** requested changes (Week 12: one `<main>` per page for accessibility); approved after he fixed it.

## 22 Nov 2026 — solar.py: production of a system
- **What I built:** `hourly_kwh` (kWh per hour), `best_window` (best block of consecutive hours in a day), `daily_kwh` (total per day), `best_day` (day with the most production).
- **My decision:** `solar.py` imports `PERFORMANCE_RATIO` from `sizing.py`, so the 0.8 lives in one place only.
- **Found:** Open-Meteo's hourly value is the average of the *previous* hour, so a value at 11:00 covers 10:00–11:00.
- **My decision:** `best_window` subtracts 1 hour from the start time so the window shown is the real one.
- **Guards:** a panel size ≤ 0 returns `[]`; an empty day or zero production returns `None`, so the page can show "no data" instead of crashing.
- **Tested:** 3 kW at 763.8 W/m² gives 1.833 kWh; a hand-made day gives a best window of 10:00–14:00 (6.73 kWh); `daily_kwh` gives 3.33 / 1.2; `best_day` picks 23 Nov (10.8 kWh).
- **Git lesson:** `git pull` on my feature branch only updated `origin/main`. I had to pull on `main` before `git merge main` brought in the new commits.
## 22 Nov 2026 — Example system on the town page
- **Goal:** show my `solar.py` functions on the live site before login and the systems pages exist.
- **My decision:** a fixed 3 kW system (tilt 30°, facing south), with the settings as constants at the top of `app.py` so they're easy to change.
- **How:** `example_system(lat, lon)` chains `get_forecast` → `hourly_kwh` → `daily_kwh` → `best_day` → `best_window`; it returns `None` if the API fails.
- **Page:** a new section in `town.html` with the best day, the best 4-hour window and a table of kWh per day, plus error and empty states (`role="alert"` / `role="status"`).
- **Tested:** Jounieh gives 8.66 / 11.27 / 8.75 kWh, best day 23 Nov, best window 09:00–13:00 (6.91 kWh). A dropped connection was logged and returned `None`, with no crash.
- **Later:** when the systems pages exist, the same chain runs with the user's real panel size on `/systems/<id>`.


## 25 Nov 2026 — System forecast page
- **Goal:** fill the "3-day production forecast" section Elia left on `/systems/<id>`.
- **My decision:** split `example_system` into `system_production(lat, lon, panel_kw, tilt, azimuth)`; the town example now calls it with the fixed 3 kW settings, so both pages share one tested calculation.
- **How:** `system_detail` gets the town's lat/lon from `get_town` (we only store `place_id`) and runs `system_production` with the system's saved values; `None` if the town or the API failed.
- **Page:** best day, best 4-hour window, kWh table with the system's own settings in the caption; error, empty and "estimate" notes.
- **Bug found:** `'production' is undefined`. The route wasn't sending `production` to the template yet; fixed by adding `production=production` to `render_template`. Lesson: `is none` is False for an undefined variable.
- **Tested:** sign up → add a 5 kW / 20° / −45° system in Jounieh → forecast shown; edit to 3 kW / 30° / 0° → same numbers as the town example.

## 23 Nov 2026 — Reviews of Elia's auth and systems PRs
- **Auth (#11):** checked hash-only passwords, `session.clear()` before login, one generic error + dummy hash (no email enumeration), POST logout, IntegrityError rollback. Approved after testing locally on a merged test branch; noted CSRF and `inject_globals` → `g.user` as follow-ups.
- **Systems (#12):** checked `get_own_system` (404/403 + log), owner from the session, `place_id` re-checked with my `get_town`, 10-system limit. Approved; noted that a failed town check on POST loses the typed values.

## 25 Nov 2026 — Review of Christ's planner PR
- **Found:** his branch was made from the main of 16 Nov → conflicts in app.py, base.html, validators.py, and it still imports `Favorite`, which no longer exists (the site would crash).
- **My decision:** requested changes: `git merge main` and keep both sides. Planner logic is correct (uses my `load_summary` → `get_winter_sun_hours` → `suggest_system`, handles `inverter_kw` None).
- **Also suggested:** a JSON route instead of scraping `/search` HTML, the `MAX_SYSTEMS` check, one helper instead of duplicated sizing code.

## 25 Nov 2026 — Live sign-up error on Render
- **Found:** 500 on sign-up; the Render log said `column user.has_solar does not exist`.
- **Cause:** `db.create_all()` creates missing tables but never adds columns; Render's `user` table was still the starter's.
- **Fix:** drop the old tables once (`DROP TABLE ... "user" CASCADE`, including the old `favorite`) and restart, so `create_all` rebuilds them. Elia (database owner) is doing it.

## 25 Nov 2026 — Next best window
- **Problem:** in the evening the pages showed today's best window (09:00–13:00), which had already passed.
- **What I built:** `solar.next_best_window(hourly, now)` keeps only the hours that haven't ended, runs `best_window` on each remaining day, and returns the one with the most kWh (or None).
- **Time zone:** `now = datetime.now(ZoneInfo("Asia/Beirut"))`, formatted like the API's times, so the text comparison works; Render runs on UTC. Added `tzdata` (Windows has no time-zone data).
- **Pages:** "Next best time" now shows the date, because the window can be tomorrow.
- **Tested:** hand data (08:00 → today, 19:00 → tomorrow, last evening → None); live Jounieh at 19:55 → 26 Nov 09:00–13:00 (7.69 kWh).