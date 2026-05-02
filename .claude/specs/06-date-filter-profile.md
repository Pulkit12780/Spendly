# Spec: Date Filter for Profile Page

## Overview
Enhance the profile page so logged-in users can filter their expense summary by a custom date range. Users enter a "from" and "to" date via a form on the profile page; the route reads these as query parameters and passes them to new DB helpers that re-compute totals and return the matching expense rows. Unfiltered (no dates entered) the page behaves exactly as the Step 4 baseline — showing all-time stats. This step depends on Step 4 being fully implemented first.

## Depends on
- Step 1 (Database Setup) — `expenses` and `users` tables, `get_db()` must exist
- Step 2 (Registration) — session population must work
- Step 4 (Profile Page Design) — `GET /profile`, `profile.html`, `get_user_by_id()`, and `get_expense_stats()` must be in place

## Routes
No new routes. The existing `GET /profile` route is enhanced to accept two optional query parameters:
- `from_date` — ISO date string (YYYY-MM-DD), inclusive lower bound
- `to_date` — ISO date string (YYYY-MM-DD), inclusive upper bound

## Database changes
No new tables or columns. Two new helper functions must be added to `database/db.py`:

- `get_expense_stats_filtered(user_id, from_date, to_date)` — same shape as `get_expense_stats()` (returns `total_count` and `total_amount`) but applies a `WHERE date BETWEEN ? AND ?` clause; if either bound is `None`, omit that side of the filter (i.e. `from_date=None` means no lower bound)
- `get_expenses_by_date_range(user_id, from_date, to_date)` — returns a list of `sqlite3.Row` objects for the matching expenses, each row including `id`, `amount`, `description`, `date`, and the category name (via a JOIN on `categories`); ordered by `date DESC`; if both bounds are `None`, returns all expenses for the user

## Templates
- **Modify:** `templates/profile.html` — add a date-filter form above the stats section; two `<input type="date">` fields (name="from_date" and name="to_date") plus a submit button; the form uses `method="get"` and `action="{{ url_for('profile') }}"` so dates appear in the URL; pre-populate inputs with the current query-param values if set; add an expenses table/list below the stats that renders the filtered expense rows; show a "No expenses found for this period." message when the list is empty

## Files to change
- `app.py` — update `profile()` to read `from_date` and `to_date` from `request.args`; call `get_expense_stats_filtered()` when at least one date is provided, `get_expense_stats()` otherwise; always call `get_expenses_by_date_range()` and pass the result to the template
- `database/db.py` — add `get_expense_stats_filtered()` and `get_expenses_by_date_range()` functions
- `templates/profile.html` — date-filter form and expenses list (see Templates above)
- `static/css/profile.css` — styles for the filter form and expenses table

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — no f-strings in SQL
- Passwords hashed with werkzeug (no password changes in this step; rule retained for consistency)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Date validation: if `from_date` is set and `to_date` is set, and `from_date > to_date`, flash an error ("'From' date cannot be after 'To' date.") and re-render with no filter applied — do not crash
- Never trust raw query param strings in SQL — always pass through parameterised placeholders
- `get_expense_stats_filtered()` must still return `total_count = 0` and `total_amount = 0.0` when no expenses match (no `None` values to the template)
- The `from_date` and `to_date` values must be echoed back into the form inputs so the user can see what filter is active
- When no filter is active the page must look and behave identically to the Step 4 baseline
- The expenses list below the stats must always reflect the same date range used for the stats

## Definition of done
- [ ] Visiting `/profile` with no query params shows all-time stats and all expenses (same as Step 4 baseline)
- [ ] Submitting the filter form with a valid date range updates both the stats and the expense list to match that range
- [ ] The "from" and "to" inputs are pre-populated with the active filter dates after submission
- [ ] If `from_date > to_date`, a flash error is shown and the unfiltered view is rendered — no crash
- [ ] A date range with no matching expenses shows `0` count, `₹0.00` total, and the "No expenses found" message
- [ ] Filtering by a single bound (only `from_date` or only `to_date`) applies just that bound correctly
- [ ] All SQL uses `?` placeholders — no string formatting
- [ ] No DB logic appears in `app.py` — all queries live in `database/db.py`
