import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "spendly.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
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
    """)
    conn.close()


def seed_db():
    conn = get_db()

    categories = [
        "Food & Dining", "Transport", "Shopping", "Entertainment",
        "Health", "Utilities", "Travel", "Other",
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO categories (name) VALUES (?)",
        [(c,) for c in categories],
    )

    users = [
        ("Nitish Kumar", "nitish@example.com", "hashed_password_placeholder"),
        ("Priya Sharma",  "priya@example.com",  "hashed_password_placeholder"),
        ("Arjun Mehta",   "arjun@example.com",  "hashed_password_placeholder"),
    ]
    for username, email, password_hash in users:
        if not conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            conn.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, password_hash),
            )

    conn.commit()

    expenses_by_user = {
        "nitish@example.com": [
            (1, 450.00,   "Lunch at Subway",          "2026-04-20"),
            (2, 120.00,   "Auto ride to office",      "2026-04-21"),
            (3, 1800.00,  "New sneakers",              "2026-04-22"),
            (5, 350.00,   "Pharmacy — vitamin tabs",   "2026-04-23"),
            (6, 800.00,   "Electricity bill",          "2026-04-24"),
        ],
        "priya@example.com": [
            (1, 210.00,  "Dinner with family",        "2026-04-21"),
            (4, 500.00,  "Movie + popcorn",           "2026-04-22"),
            (2, 80.00,   "Metro top-up",              "2026-04-23"),
        ],
        "arjun@example.com": [
            (7, 12500.00, "Goa trip flights",         "2026-04-18"),
            (1, 650.00,   "Biryani for the team",     "2026-04-25"),
        ],
    }

    for email, rows in expenses_by_user.items():
        user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            continue
        uid = user["id"]
        if conn.execute("SELECT 1 FROM expenses WHERE user_id = ? LIMIT 1", (uid,)).fetchone():
            continue
        conn.executemany(
            "INSERT INTO expenses (user_id, category_id, amount, description, date) VALUES (?, ?, ?, ?, ?)",
            [(uid, cat_id, amt, desc, dt) for cat_id, amt, desc, dt in rows],
        )

    conn.commit()
    conn.close()
