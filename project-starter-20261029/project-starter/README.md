# Team Project Starter (Flask)

A starter for the GIN446 team project: a full-stack Flask web app whose content
comes from a free external API. It runs out of the box on sample data so you can
deploy it first, then make it your own.

**You build the authentication yourself.** The starter gives you the structure,
the API client, the templates, the data models and the database wiring - but the
sign-up / log-in / log-out / session logic is left as **stubs for you to
implement** (see the "Sessions & Login" slides).

## What it does (starter state)
- Browse sample items, search, open a detail page.
- A `User` and a `Favorite` table are defined; `favorites` routes are a worked
  example that uses the session (they work once you implement log-in).
- Auth routes exist but are empty - that's your job.

## Run it in VS Code
1. Open this folder in VS Code.
2. Create and activate a virtual environment:
   - Windows: `python -m venv venv` then `venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv venv` then `source venv/bin/activate`
3. `pip install -r requirements.txt`
4. Create the database tables: `python reset_db.py`
5. Run the app: `flask run --debug`
6. Open `http://127.0.0.1:5000`.

## The database
- `models.py` is the single source of truth for your tables (`User`, `Favorite`).
- `python reset_db.py` drops and recreates the tables from `models.py` - run it
  after you change a model during development.
- The app also calls `db.create_all()` on startup, so on Render the tables are
  created automatically on first deploy (no script to run there).

## Your work (the TODOs)
- **Authentication** - implement `signup`, `login`, `logout` and sessions in
  `app.py` (hash passwords, store `session["user_id"]`, gate routes, clear on
  logout). Validators are provided in `validators.py`.
- **`api_client.py`** - replace the sample data with calls to *your* chosen API.
  Keep the shapes: `search(q)` -> list of `{id, title, image}`;
  `get_item(id)` -> one `{id, title, image, description}`.
- **`models.py`** - rename/extend `Favorite` (or add your own table) to fit your app;
  then run `python reset_db.py`.
- **`templates/`** - change the wording and show the fields your API returns.

## Structure
```
app.py            routes; auth stubs you implement (the controller)
api_client.py     all calls to your external API (edit this)
validators.py     server-side validation for sign-up / log-in (provided)
models.py         database models: User, Favorite
reset_db.py       (re)create the tables locally
templates/        pages (the view)
static/style.css
requirements.txt  packages
Procfile          start command for Render (gunicorn)
```

## Deploy
Push to your **team GitHub repo**, then follow the **"Set Up Your Team's Database
on Render"** activity to add a PostgreSQL database and go live.
