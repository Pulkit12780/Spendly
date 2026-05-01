# Spec: Profile Page Design

## Overview
Implement the user profile page so that logged-in users can see their account details and a high-level summary of their spending activity. This step converts the stub `GET /profile` route into a real, session-protected page that displays the user's username, email, and join date alongside aggregate expense stats (total expenses logged and total amount spent). It also wires up conditional nav links in `base.html` so authenticated and unauthenticated users see the appropriate navbar.

## Depends on
- Step 1 (Database Setup) — `users` and `expenses` tables, `get_db()` must exist
- Step 2 (Registration) — `session["user_id"]` population and `create_user()` must exist

## Routes
- `GET /profile` — renders the profile page for the currently logged-in user; redirects to `/login` if session is absent — logged-in only

## Database changes
No new tables or columns. Two new helper functions must be added to `database/db.py`:

- `get_user_by_id(user_id)` — returns a single `sqlite3.Row` for the given id, or `None` if not found
- `get_expense_stats(user_id)` — returns a dict (or `sqlite3.Row`) with two fields: `total_count` (INTEGER) and `total_amount` (REAL); returns zeroed values if the user has no expenses

## Templates
- **Create:** `templates/profile.html` — extends `base.html`; displays username, email, member-since date, total expenses count, and total amount spent
- **Modify:** `templates/base.html` — add conditional nav links: show "Profile" and "Sign out" when `session.user_id` is set; show "Sign in" and "Get started" otherwise

## Files to change
- `app.py` — replace stub `profile()` with a real route that guards on session, fetches user + stats, and renders `profile.html`
- `database/db.py` — add `get_user_by_id()` and `get_expense_stats()` functions
- `templates/base.html` — add conditional navbar links for logged-in vs. guest state

## Files to create
- `templates/profile.html` — profile page template
- `static/css/profile.css` — styles scoped to the profile page only; imported in `profile.html` via a `{% block extra_css %}` block in `base.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — no f-strings in SQL
- Passwords hashed with werkzeug (no password changes in this step; rule retained for consistency)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `GET /profile` must call `abort(401)` or `redirect(url_for('login'))` if `session.get("user_id")` is not set — never render the page for unauthenticated users
- DB logic (both new helpers) belongs entirely in `database/db.py` — the route function only calls them and passes results to the template
- `get_expense_stats()` must return `total_count = 0` and `total_amount = 0.0` when the user has no expenses (no `None` values reaching the template)
- `base.html` must use `session.get("user_id")` (not a template variable) to decide which nav links to render — no extra context variable required
- The `{% block extra_css %}` extension point must be added to `base.html` if it does not already exist, so page-specific stylesheets can be injected

## Definition of done
- [ ] Visiting `/profile` while logged in (via registration) shows the user's username, email, and join date
- [ ] Visiting `/profile` while **not** logged in redirects to `/login` (no profile content is shown)
- [ ] The profile page shows the correct total number of expenses and total amount spent for the logged-in user
- [ ] A user with zero expenses sees `0` expenses and `₹0.00` (or equivalent) — no crash or blank value
- [ ] The navbar shows "Profile" and "Sign out" links when a session is active
- [ ] The navbar shows "Sign in" and "Get started" when no session is active
- [ ] All SQL in `db.py` uses `?` placeholders, not string formatting
- [ ] `profile.css` is loaded only on the profile page, not on every page
