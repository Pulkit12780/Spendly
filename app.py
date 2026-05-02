import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from database.db import (
    init_db, seed_db, create_user,
    get_user_by_id, get_expense_stats,
    get_expense_stats_filtered, get_expenses_by_date_range,
)

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"  # use env var in production


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register")
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))
    return render_template("register.html")


@app.route("/register", methods=["POST"])
def register_post():
    username = request.form.get("username", "").strip()
    email    = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm  = request.form.get("confirm_password", "")

    if not username or not email or not password:
        flash("All fields are required.")
        return redirect(url_for("register"))

    if password != confirm:
        flash("Passwords do not match.")
        return redirect(url_for("register"))

    try:
        user_id = create_user(username, email, password)
    except sqlite3.IntegrityError:
        flash("An account with that email already exists.")
        return redirect(url_for("register"))

    session["user_id"]  = user_id
    session["username"] = username
    return redirect(url_for("landing"))


@app.route("/login")
def login():
    return render_template("login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    return "Logout — coming in Step 3"


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])
    from_date = request.args.get("from_date", "").strip() or None
    to_date   = request.args.get("to_date", "").strip() or None

    if from_date and to_date and from_date > to_date:
        flash("'From' date cannot be after 'To' date.")
        from_date = to_date = None

    if from_date or to_date:
        stats = get_expense_stats_filtered(session["user_id"], from_date, to_date)
    else:
        stats = get_expense_stats(session["user_id"])

    expenses = get_expenses_by_date_range(session["user_id"], from_date, to_date)

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        expenses=expenses,
        from_date=from_date or "",
        to_date=to_date or "",
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    init_db()
    seed_db()
    app.run(debug=True, port=5001)
