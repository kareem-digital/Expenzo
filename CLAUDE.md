# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

"Expenzo" is a Flask-based personal expense tracker, built incrementally as a step-by-step learning exercise (see `file.txt` for the running log of past feature prompts/commits). Many pieces are intentionally left as stubs for future steps — check comments before assuming something is unimplemented by accident.

## Commands

Activate the virtualenv first (already created at `venv/`):

```
# from a POSIX shell
source venv/Scripts/activate      # Windows venv on git-bash
# from PowerShell
venv\Scripts\Activate.ps1
```

Run the app (serves on port 5001):
```
python app.py
```

Install/sync dependencies:
```
pip install -r requirements.txt
```

Run tests (pytest + pytest-flask are installed, but no test files exist yet — add them under a `tests/` directory):
```
pytest
pytest path/to/test_file.py::test_name   # single test
```

## Architecture

- **`app.py`** — single-file Flask app. All routes are defined here directly (no blueprints). Routes fall into two groups:
  - Implemented pages: `/`, `/register`, `/login`, `/terms`, `/privacy` — each renders a template from `templates/`.
  - Placeholder routes (`/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`) — return plain placeholder strings and are explicitly marked for later steps. Don't "fix" these into real implementations unless asked.

- **`database/db.py`** — currently just a spec comment, not yet implemented. When building it out, it should expose `get_db()` (SQLite connection with `row_factory` and foreign keys enabled), `init_db()` (create tables with `CREATE TABLE IF NOT EXISTS`), and `seed_db()` (sample dev data). The SQLite file (`expense_tracker.db`) is gitignored, so it's created/seeded locally rather than committed.

- **Templates** (`templates/`) — Jinja2, all extending `base.html`, which provides the shared nav/footer chrome and pulls in `static/css/style.css` and `static/js/main.js` via `url_for`. Route-specific styles/scripts use the `{% block head %}` / `{% block scripts %}` blocks. Follow this same base.html extension pattern for any new page.

- **`static/js/main.js`** — vanilla JS only, no frameworks/libraries are used anywhere in this project. Current content wires up the "how it works" video modal (open/close, stop video on close).

- **`static/css/style.css`** — single global stylesheet for the whole site; there is no per-page CSS split despite what old prompts in `file.txt` reference (e.g. a `landing.css` that doesn't actually exist).

## Working style notes

- `file.txt` contains a sequence of past feature request prompts (each ending with the `git commit -m "..."` message that was used). It's a historical log, not an active task list — don't treat its contents as pending work unless the user says so.
