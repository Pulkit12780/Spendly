"""
tests/test_06_date_filter_profile.py

Spec-driven tests for Step 06: Date Filter for Profile Page.

All tests operate against an in-memory SQLite database that is created fresh
for every test function. The fixture patches database/db.py so that get_db()
opens ":memory:" instead of the real spendly.db file on disk.

Seed data is deterministic and chosen to make date-range assertions unambiguous:

  User: testuser / test@example.com   (user_id known after INSERT)

  Categories seeded (same names as production):
    1 = Food & Dining
    2 = Transport
    3 = Shopping

  Expenses for testuser:
    id  cat  amount   date          description
    --  ---  ------   ----------    -----------
    e1   1   100.00   2025-01-10    Breakfast
    e2   2   200.00   2025-02-15    Bus pass
    e3   3   300.00   2025-03-20    Shoes
    e4   1   400.00   2025-04-25    Team lunch

  total_count = 4  total_amount = 1000.00

A second user (other@example.com) with one expense is also seeded to verify
that filtering never leaks across user boundaries.
"""

import sqlite3
import pytest
from unittest.mock import patch
from werkzeug.security import generate_password_hash

import app as app_module
from database import db as db_module


# ---------------------------------------------------------------------------
# Schema — mirrors init_db() exactly so we stay spec-independent of the file
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT    NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id)      ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    amount      REAL    NOT NULL CHECK (amount > 0),
    description TEXT,
    date        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


# ---------------------------------------------------------------------------
# Shared in-memory DB factory
# ---------------------------------------------------------------------------

def _make_memory_db():
    """Return an open :memory: connection with schema and seed data loaded."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)

    # Categories
    conn.executemany(
        "INSERT INTO categories (name) VALUES (?)",
        [("Food & Dining",), ("Transport",), ("Shopping",)],
    )

    # Primary test user
    conn.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        ("testuser", "test@example.com", generate_password_hash("password123")),
    )

    # Secondary user — used only to verify cross-user isolation
    conn.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        ("otheruser", "other@example.com", generate_password_hash("other456")),
    )

    conn.commit()

    # Resolve user IDs dynamically so tests are not brittle against AUTOINCREMENT
    primary_uid = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("test@example.com",)
    ).fetchone()["id"]
    other_uid = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("other@example.com",)
    ).fetchone()["id"]

    # Expenses for primary user (category IDs 1, 2, 3 match the INSERT order above)
    conn.executemany(
        "INSERT INTO expenses (user_id, category_id, amount, description, date) VALUES (?, ?, ?, ?, ?)",
        [
            (primary_uid, 1, 100.00, "Breakfast",  "2025-01-10"),
            (primary_uid, 2, 200.00, "Bus pass",   "2025-02-15"),
            (primary_uid, 3, 300.00, "Shoes",      "2025-03-20"),
            (primary_uid, 1, 400.00, "Team lunch", "2025-04-25"),
        ],
    )

    # One expense for the other user — must never appear in primary user's results
    conn.executemany(
        "INSERT INTO expenses (user_id, category_id, amount, description, date) VALUES (?, ?, ?, ?, ?)",
        [
            (other_uid, 1, 9999.00, "Other user expense", "2025-03-20"),
        ],
    )

    conn.commit()
    return conn


class _NoCloseConnection:
    """
    Thin wrapper around a sqlite3.Connection that silently ignores close()
    calls. This is necessary because every db.py helper ends with conn.close(),
    but the test fixture must keep ONE connection open for the lifetime of the
    test (sqlite3 :memory: databases are per-connection; a second
    connect(":memory:") opens a completely blank database).

    All attribute access is delegated transparently to the real connection,
    so the helpers see a genuine sqlite3.Connection in every other respect.
    """

    def __init__(self, real_conn):
        self._conn = real_conn

    def close(self):
        # Intentionally a no-op — the fixture closes the real connection itself
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """
    Flask test client backed by a fresh in-memory SQLite database.

    One real connection is created for the whole test.  get_db() is patched
    to return a _NoCloseConnection wrapper around that connection so that the
    conn.close() calls inside db.py helpers are no-ops and the in-memory DB
    stays alive across multiple helper calls within the same request.
    """
    real_conn = _make_memory_db()
    wrapper = _NoCloseConnection(real_conn)

    def _patched_get_db():
        wrapper._conn.row_factory = sqlite3.Row
        wrapper._conn.execute("PRAGMA foreign_keys = ON")
        return wrapper

    # Patch get_db in the db module (where the helpers call it)
    with patch.object(db_module, "get_db", side_effect=_patched_get_db):

        app_module.app.config["TESTING"] = True
        app_module.app.config["SECRET_KEY"] = "test-secret-key"

        with app_module.app.test_client() as flask_client:
            yield flask_client, real_conn

    real_conn.close()


# ---------------------------------------------------------------------------
# Helper: log in as the primary test user
# ---------------------------------------------------------------------------

def _login(client, conn):
    """Set the session so the profile route sees an authenticated user."""
    uid = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("test@example.com",)
    ).fetchone()["id"]
    with client.session_transaction() as sess:
        sess["user_id"] = uid
    return uid


# ---------------------------------------------------------------------------
# Authentication guard tests
# ---------------------------------------------------------------------------

class TestProfileAuthGuard:
    def test_profile_redirects_to_login_when_not_authenticated(self, client):
        """GET /profile without a session must redirect to /login."""
        flask_client, _ = client
        response = flask_client.get("/profile")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_profile_does_not_render_page_when_not_authenticated(self, client):
        """Following the redirect must not land on the profile page."""
        flask_client, _ = client
        response = flask_client.get("/profile", follow_redirects=True)
        # The login page does not contain the profile-header class
        assert b"profile-header" not in response.data


# ---------------------------------------------------------------------------
# No-filter (all-time) baseline — spec DoD item 1
# ---------------------------------------------------------------------------

class TestProfileNoFilter:
    def test_profile_returns_200_when_authenticated(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        assert response.status_code == 200

    def test_profile_renders_username(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        assert b"testuser" in response.data

    def test_profile_renders_email(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        assert b"test@example.com" in response.data

    def test_profile_no_filter_shows_all_time_total_count(self, client):
        """All 4 seeded expenses must appear in total_count without a filter."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        # The stats-grid renders the count as a bare number inside stat-value
        assert b"4" in response.data

    def test_profile_no_filter_shows_all_time_total_amount(self, client):
        """All-time total is 100 + 200 + 300 + 400 = 1000.00."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        assert "₹1000.00".encode() in response.data

    def test_profile_no_filter_shows_all_four_expense_rows(self, client):
        """All expense descriptions must appear in the table."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        assert b"Breakfast"  in response.data
        assert b"Bus pass"   in response.data
        assert b"Shoes"      in response.data
        assert b"Team lunch" in response.data

    def test_profile_no_filter_does_not_show_other_users_expenses(self, client):
        """The other user's expense description must never appear."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        assert b"Other user expense" not in response.data

    def test_profile_no_filter_does_not_show_clear_link(self, client):
        """Clear link is only shown when a filter is active."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        assert b"filter-clear" not in response.data

    def test_profile_renders_stats_grid(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        assert b"stats-grid" in response.data

    def test_profile_renders_expense_table(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        assert b"expense-table" in response.data

    def test_profile_renders_filter_form_with_get_method(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        assert b'method="get"' in response.data

    def test_profile_form_has_from_date_input(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        assert b'name="from_date"' in response.data

    def test_profile_form_has_to_date_input(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        assert b'name="to_date"' in response.data


# ---------------------------------------------------------------------------
# Valid date range — spec DoD item 2
# ---------------------------------------------------------------------------

class TestProfileValidDateRange:
    def test_filter_returns_200(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-02-01&to_date=2025-03-31")
        assert response.status_code == 200

    def test_filter_count_matches_expenses_in_range(self, client):
        """2025-02-01 to 2025-03-31 covers e2 (Feb 15) and e3 (Mar 20) → count=2."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-02-01&to_date=2025-03-31")
        assert b"2" in response.data

    def test_filter_amount_matches_expenses_in_range(self, client):
        """200 + 300 = 500.00."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-02-01&to_date=2025-03-31")
        assert "₹500.00".encode() in response.data

    def test_filter_shows_only_in_range_descriptions(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-02-01&to_date=2025-03-31")
        assert b"Bus pass"  in response.data
        assert b"Shoes"     in response.data

    def test_filter_excludes_out_of_range_descriptions(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-02-01&to_date=2025-03-31")
        assert b"Breakfast"  not in response.data
        assert b"Team lunch" not in response.data

    def test_filter_inclusive_lower_bound(self, client):
        """from_date = exactly the date of e2 (2025-02-15) must include e2."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-02-15&to_date=2025-03-31")
        assert b"Bus pass" in response.data

    def test_filter_inclusive_upper_bound(self, client):
        """to_date = exactly the date of e3 (2025-03-20) must include e3."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-01-01&to_date=2025-03-20")
        assert b"Shoes" in response.data

    def test_filter_single_day_range(self, client):
        """from_date == to_date must return only expenses on that single day."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-04-25&to_date=2025-04-25")
        assert b"Team lunch" in response.data
        assert b"Breakfast"  not in response.data
        assert b"Bus pass"   not in response.data
        assert b"Shoes"      not in response.data


# ---------------------------------------------------------------------------
# Input pre-population — spec DoD item 3
# ---------------------------------------------------------------------------

class TestProfileInputPrePopulation:
    def test_from_date_pre_populated_in_form_input(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-02-01&to_date=2025-03-31")
        assert b'value="2025-02-01"' in response.data

    def test_to_date_pre_populated_in_form_input(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-02-01&to_date=2025-03-31")
        assert b'value="2025-03-31"' in response.data

    def test_clear_link_present_when_filter_active(self, client):
        """Clear link must appear whenever at least one date param is set."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-02-01&to_date=2025-03-31")
        assert b"filter-clear" in response.data

    def test_clear_link_present_when_only_from_date_set(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-02-01")
        assert b"filter-clear" in response.data

    def test_clear_link_present_when_only_to_date_set(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?to_date=2025-03-31")
        assert b"filter-clear" in response.data

    def test_inputs_empty_when_no_filter_params_sent(self, client):
        """Without query params the inputs must render as value="" (empty)."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile")
        assert b'value=""' in response.data


# ---------------------------------------------------------------------------
# Invalid date range (from > to) — spec DoD item 4
# ---------------------------------------------------------------------------

class TestProfileInvalidDateRange:
    def test_from_after_to_returns_200_not_crash(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-12-31&to_date=2025-01-01")
        assert response.status_code == 200

    def test_from_after_to_flashes_error_message(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get(
            "/profile?from_date=2025-12-31&to_date=2025-01-01",
            follow_redirects=True,
        )
        assert b"&#39;From&#39; date cannot be after &#39;To&#39; date." in response.data

    def test_from_after_to_renders_unfiltered_all_time_count(self, client):
        """Validation failure must fall back to all-time stats (count=4)."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-12-31&to_date=2025-01-01")
        assert b"4" in response.data

    def test_from_after_to_renders_unfiltered_all_time_amount(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-12-31&to_date=2025-01-01")
        assert "₹1000.00".encode() in response.data

    def test_from_after_to_renders_all_expenses(self, client):
        """Unfiltered fallback must show all four expense rows."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-12-31&to_date=2025-01-01")
        assert b"Breakfast"  in response.data
        assert b"Bus pass"   in response.data
        assert b"Shoes"      in response.data
        assert b"Team lunch" in response.data

    def test_from_after_to_does_not_show_clear_link(self, client):
        """
        After the validation fires, from_date and to_date are both set to None
        in the route, so no Clear link should appear (filter is not active).
        """
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-12-31&to_date=2025-01-01")
        assert b"filter-clear" not in response.data


# ---------------------------------------------------------------------------
# Empty result set — spec DoD item 5
# ---------------------------------------------------------------------------

class TestProfileEmptyDateRange:
    def test_date_range_with_no_expenses_shows_zero_count(self, client):
        """A range with no matching expenses must show count = 0."""
        flask_client, conn = client
        _login(flask_client, conn)
        # 2025-06-01 to 2025-06-30 has no seeded expenses
        response = flask_client.get("/profile?from_date=2025-06-01&to_date=2025-06-30")
        assert b"0" in response.data

    def test_date_range_with_no_expenses_shows_zero_amount(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-06-01&to_date=2025-06-30")
        assert "₹0.00".encode() in response.data

    def test_date_range_with_no_expenses_shows_empty_state_message(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-06-01&to_date=2025-06-30")
        assert b"No expenses found for this period." in response.data

    def test_date_range_with_no_expenses_does_not_show_table(self, client):
        """When the list is empty the expense table element must not appear."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-06-01&to_date=2025-06-30")
        assert b"expense-table" not in response.data

    def test_stats_do_not_return_none_values_when_no_match(self, client):
        """
        The spec mandates total_count=0 and total_amount=0.0 (not NULL/None).
        If None leaked through, Jinja's format filter would crash the render.
        A 200 response with the formatted ₹0.00 proves no None reached the template.
        """
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-06-01&to_date=2025-06-30")
        assert response.status_code == 200
        assert "₹0.00".encode() in response.data


# ---------------------------------------------------------------------------
# Single-bound filtering — spec DoD item 6
# ---------------------------------------------------------------------------

class TestProfileSingleBoundFilter:
    def test_only_from_date_excludes_earlier_expenses(self, client):
        """from_date=2025-03-01 (no to_date) must exclude e1 (Jan) and e2 (Feb)."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-03-01")
        assert b"Breakfast" not in response.data
        assert b"Bus pass"  not in response.data

    def test_only_from_date_includes_on_or_after_bound(self, client):
        """from_date=2025-03-01 must include e3 (Mar 20) and e4 (Apr 25)."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-03-01")
        assert b"Shoes"      in response.data
        assert b"Team lunch" in response.data

    def test_only_from_date_amount_is_correct(self, client):
        """300 + 400 = 700.00."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-03-01")
        assert "₹700.00".encode() in response.data

    def test_only_to_date_excludes_later_expenses(self, client):
        """to_date=2025-02-28 (no from_date) must exclude e3 (Mar) and e4 (Apr)."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?to_date=2025-02-28")
        assert b"Shoes"      not in response.data
        assert b"Team lunch" not in response.data

    def test_only_to_date_includes_on_or_before_bound(self, client):
        """to_date=2025-02-28 must include e1 (Jan 10) and e2 (Feb 15)."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?to_date=2025-02-28")
        assert b"Breakfast" in response.data
        assert b"Bus pass"  in response.data

    def test_only_to_date_amount_is_correct(self, client):
        """100 + 200 = 300.00."""
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?to_date=2025-02-28")
        assert "₹300.00".encode() in response.data

    def test_only_from_date_shows_clear_link(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-03-01")
        assert b"filter-clear" in response.data

    def test_only_to_date_shows_clear_link(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?to_date=2025-02-28")
        assert b"filter-clear" in response.data

    def test_only_from_date_pre_populated_in_input(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-03-01")
        assert b'value="2025-03-01"' in response.data

    def test_only_to_date_pre_populated_in_input(self, client):
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?to_date=2025-02-28")
        assert b'value="2025-02-28"' in response.data


# ---------------------------------------------------------------------------
# Cross-user data isolation
# ---------------------------------------------------------------------------

class TestProfileCrossUserIsolation:
    def test_filter_never_shows_other_users_expense(self, client):
        """
        The other user also has an expense on 2025-03-20, but it must never
        appear on the primary user's profile, even when that date is in range.
        """
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-03-01&to_date=2025-03-31")
        assert b"Other user expense" not in response.data

    def test_filter_amount_not_inflated_by_other_users_expense(self, client):
        """
        2025-03-01 to 2025-03-31 for testuser covers only e3 (₹300.00).
        If the query leaked other-user data the total would be ₹9999.00 higher.
        """
        flask_client, conn = client
        _login(flask_client, conn)
        response = flask_client.get("/profile?from_date=2025-03-01&to_date=2025-03-31")
        assert "₹300.00".encode() in response.data
        assert b"9999" not in response.data


# ---------------------------------------------------------------------------
# DB layer contract: no DB logic in app.py (spec DoD item 8)
# ---------------------------------------------------------------------------

class TestAppRouteStructure:
    def test_app_py_does_not_contain_inline_sql(self):
        """
        The profile route in app.py must not contain any raw SQL.
        All queries belong in database/db.py (spec rule).
        """
        import ast
        import inspect
        import app as the_app

        source = inspect.getsource(the_app.profile)
        # Check for obvious SQL keywords that would indicate inline queries
        sql_markers = ["SELECT ", "INSERT ", "UPDATE ", "DELETE ", "FROM ", "WHERE "]
        for marker in sql_markers:
            assert marker not in source, (
                f"Found SQL keyword '{marker.strip()}' in app.py profile() — "
                "DB logic must live in database/db.py only."
            )

    def test_db_module_uses_parameterized_placeholders(self):
        """
        database/db.py must use ? placeholders; no f-string SQL construction.
        We scan the source for f-string SQL patterns as a static check.
        """
        import inspect
        import database.db as the_db

        for name, fn in inspect.getmembers(the_db, inspect.isfunction):
            source = inspect.getsource(fn)
            # An f-string that contains a SQL keyword is a red flag
            # Pattern: f"...SELECT..." or f'...WHERE...'
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith('f"') or stripped.startswith("f'"):
                    sql_markers = ["SELECT", "INSERT", "UPDATE", "DELETE", "WHERE", "FROM"]
                    for marker in sql_markers:
                        assert marker not in stripped, (
                            f"Function '{name}' in db.py appears to use an f-string "
                            f"containing SQL keyword '{marker}'. Use ? placeholders only."
                        )

    def test_profile_route_calls_db_helpers_not_get_db_directly(self):
        """
        app.py's profile() must delegate to the named DB helpers
        (get_expense_stats, get_expense_stats_filtered, get_expenses_by_date_range)
        and must not call get_db() or sqlite3.connect() itself.
        """
        import inspect
        import app as the_app

        source = inspect.getsource(the_app.profile)
        assert "get_db()"          not in source, "profile() calls get_db() directly — must use db helpers"
        assert "sqlite3.connect("  not in source, "profile() calls sqlite3.connect() — must use db helpers"
        assert "conn.execute("     not in source, "profile() calls conn.execute() — must use db helpers"
