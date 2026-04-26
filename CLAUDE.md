# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Spendly** — a personal expense tracking web app targeting Indian users (₹). Built with Flask + Jinja2 templating. Currently in active development; auth and DB layers are stubs awaiting implementation.

## Common Commands

```bash
# Create and activate virtual environment
python -m venv myenv && source myenv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server (http://localhost:5001)
python app.py

# Run tests
pytest

# Run a single test file
pytest tests/test_routes.py
```

No linter is configured yet. The `.gitignore` excludes `myenv/`, `*.db`, `.env`, and `__pycache__/`.

## Architecture

**Stack:** Flask 3.1 · Jinja2 templates · Vanilla JS · SQLite (planned) · pytest

### Request Flow

```
Browser → Flask routes (app.py) → Jinja2 templates (templates/) → Static assets (static/)
                                        ↓
                                 database/db.py  (SQLite — not yet implemented)
```

### Key Files

| File | Role |
|---|---|
| `app.py` | All Flask routes and app config (debug=True, port=5001) |
| `database/db.py` | Stubs for `get_db()`, `init_db()`, `seed_db()` — needs implementation |
| `templates/base.html` | Master layout: sticky navbar, footer, CSS/JS includes |
| `static/css/style.css` | Global design tokens (CSS variables), forms, nav, buttons |
| `static/css/landing.css` | Landing page hero, feature cards, video modal |

### Routes

**Implemented (render templates):** `/`, `/register`, `/login`, `/terms`, `/privacy`

**Stubs (return placeholder strings, Steps 3–9):** `/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`

### Database Layer (`database/db.py`)

Three functions to implement:
- `get_db()` — SQLite connection with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`
- `init_db()` — `CREATE TABLE IF NOT EXISTS` schema setup
- `seed_db()` — inserts sample data for development

### Frontend Conventions

- Templates extend `base.html` using `{% extends "base.html" %}` / `{% block content %}`.
- Static assets referenced via `url_for('static', filename='css/style.css')`.
- CSS custom properties defined in `style.css` — use these variables (e.g. `--color-accent`, `--color-paper`) rather than hardcoded values.
- Forms POST to their own route (handlers not yet wired on the Flask side).
