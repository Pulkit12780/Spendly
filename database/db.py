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


def create_user(username, email, password):
    from werkzeug.security import generate_password_hash
    password_hash = generate_password_hash(password, method="pbkdf2:sha256")
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (username, email, password_hash),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def get_user_by_email(email):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def get_expense_stats(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS total_count, COALESCE(SUM(amount), 0.0) AS total_amount "
        "FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return {"total_count": row["total_count"], "total_amount": row["total_amount"]}


def get_expense_stats_filtered(user_id, from_date, to_date):
    sql = (
        "SELECT COUNT(*) AS total_count, COALESCE(SUM(amount), 0.0) AS total_amount "
        "FROM expenses WHERE user_id = ?"
    )
    params = [user_id]
    if from_date:
        sql += " AND date >= ?"
        params.append(from_date)
    if to_date:
        sql += " AND date <= ?"
        params.append(to_date)
    conn = get_db()
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return {"total_count": row["total_count"], "total_amount": row["total_amount"]}


def get_expenses_by_date_range(user_id, from_date, to_date):
    sql = (
        "SELECT e.id, e.amount, e.description, e.date, c.name AS category "
        "FROM expenses e JOIN categories c ON e.category_id = c.id "
        "WHERE e.user_id = ?"
    )
    params = [user_id]
    if from_date:
        sql += " AND e.date >= ?"
        params.append(from_date)
    if to_date:
        sql += " AND e.date <= ?"
        params.append(to_date)
    sql += " ORDER BY e.date DESC"
    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows
