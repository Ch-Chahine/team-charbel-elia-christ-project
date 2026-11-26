# AI Log — Christ Merheb (202401517)

**Tool:** Claude (Anthropic) — AI Level 2 (Assisted).
**AI's role:** reviewed my appliance and planner code, found bugs, suggested fixes and new code.
**My role:** I read and understood every line before committing, ran the tests below myself, and can explain each route.

> Before each commit: replace every *(write what you saw)* with what actually happened when you tested.

---

## 26 Nov 2026 — Planner and appliance fixes (`feature/planner-fixes`)
- **Asked:** a review of my appliance CRUD and planner pages against the project plan.
- **Bugs found and fixed:**
  - Autonomy select reset to "0 days" after a form error: the template compared the text `"2"` with the number `2`. Now every value is compared as text.
  - Town box was empty when coming back to the planner (`town_name` was never sent). The route now looks the name up with `get_town`.
  - "Install" created a new system on every click and ignored `MAX_SYSTEMS`. It now checks for the same planned system and the limit, and the button disables itself.
  - Every planner submit added a new `Plan` row. The user's plan is now updated in place.
  - The town search read the HTML of `/search`. It now calls a small JSON route `/api/towns` (same `validate_search` rules).
- **Other changes:** validation moved to `validators.py` (`validate_appliance`, per-field errors, refuses `nan`/`inf`); `get_own_appliance` logs 403s (A09); `SQLAlchemyError` instead of `Exception`; 50-appliance limit (A06); "Add typical appliances" button; architecture drawing (SVG with `title`/`desc`); disclaimer "Estimate only — confirm with a certified installer"; `_csrf.html` include ready for Elia's CSRFProtect.
- **Tested:**
  - Planner with autonomy 2 and panel 50 W → error shown, autonomy still 2. *(write what you saw)*
  - Come back to /planner → town name shown. *(write what you saw)*
  - Double-click "I installed this" → only one system. *(write what you saw)*
  - Appliance with day 13 h + night 12 h → error under "night hours". *(write what you saw)*
  - Log in as user B, open /appliances/<A's id>/edit → 403, warning in the terminal. *(write what you saw)*
