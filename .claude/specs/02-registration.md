# Spec: Registration

## Overview
Implement user registration so new visitors can create a Spendly account. This step converts the existing stub `GET /register` page into a fully functional form that validates input, hashes the password, persists the user to the database, and starts a session so the user is immediately logged in after signing up.

## Depends on
- Step 1 (Database Setup) — `users` table and `get_db()` must exist

## Routes
- `GET /register` — already exists, renders `register.html` — public (update to redirect logged-in users)
- `POST /register` — new, processes the registration form — public

## Database changes
No new tables. The `users` table (id, username, email, password_hash, created_at) is already created in Step 1.

Two new helper functions must be added to `database/db.py`:
- `create_user(username, email, password)` — hashes the password and inserts a new row; returns the new user id; raises `sqlite3.IntegrityError` on duplicate email
- `get_user_by_email(email)` — returns a single `sqlite3.Row` or `None`

## Templates
- **Modify:** `templates/register.html` — replace placeholder content with a form containing fields: username, email, password, confirm password; display flash messages for errors and success
- **Modify:** `templates/base.html` — ensure `get_flashed_messages()` is rendered (add flash block if not already present)

## Files to change
- `app.py` — add `app.secret_key`, update `GET /register` to redirect if session active, add `POST /register` route
- `database/db.py` — add `create_user()` and `get_user_by_email()` functions
- `templates/register.html` — add the registration form and flash message display
- `templates/base.html` — add flash message rendering block if missing

## Files to create
- `static/css/auth.css` — styles scoped to the registration (and later login) page; imported only on auth pages

## New dependencies
No new dependencies. Use `werkzeug.security.generate_password_hash` (already available via Flask's dependency tree).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — no f-strings in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash` using `pbkdf2:sha256`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `app.secret_key` must be set before any session usage; use a hard-coded dev string for now (e.g. `"spendly-dev-secret"`) — a comment noting it should come from env in production is acceptable
- After successful registration, store `session["user_id"]` and `session["username"]`, then redirect to `/` (landing) or a future dashboard stub
- On duplicate email, flash a user-friendly error and re-render the form (do not expose the raw `IntegrityError` to the template)
- On password mismatch (confirm ≠ password), flash an error before hitting the database
- `GET /register` must redirect to `/` if `session.get("user_id")` is already set
- Use `flask.flash()` for all user-facing errors — no inline error variables passed to the template

## Definition of done
- [ ] Visiting `/register` shows a form with username, email, password, and confirm-password fields
- [ ] Submitting the form with valid, unique data creates a new row in the `users` table with a hashed (non-plaintext) password
- [ ] After successful registration the user is redirected and `session["user_id"]` is set
- [ ] Submitting with a duplicate email shows a flash error and does not crash
- [ ] Submitting with mismatched passwords shows a flash error and does not hit the database
- [ ] Submitting with any empty field shows a flash error
- [ ] A logged-in user visiting `/register` is redirected away (not shown the form again)
- [ ] All queries in `db.py` use `?` placeholders, not string formatting
