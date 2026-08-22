import sqlite3

from flask import Flask, render_template, request, redirect, url_for, flash, abort, session
from werkzeug.security import check_password_hash

from database.db import init_db, seed_db, create_user, get_user_by_email

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    if request.method != "POST":
        abort(405)

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not email or not password or not confirm_password:
        flash("All fields are required.", "error")
        return render_template("register.html")

    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return render_template("register.html")

    try:
        create_user(name, email, password)
    except sqlite3.IntegrityError:
        flash("Email already registered.", "error")
        return render_template("register.html")

    flash("Account created successfully! Please sign in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    if request.method != "POST":
        abort(405)

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email or not password:
        flash("Please enter both email and password.", "error")
        return render_template("login.html")

    user = get_user_by_email(email)

    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.", "error")
        return render_template("login.html")

    session["user_id"] = user["id"]
    flash("Signed in successfully.", "success")
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name": "Demo User",
        "email": "demo@expenzo.com",
        "initials": "DU",
        "member_since": "January 2026",
    }

    stats = [
        {"label": "Total spent", "value": "₹5,330.50", "delta": "this month", "delta_style": "muted"},
        {"label": "Transactions", "value": "8", "delta": "this month", "delta_style": "muted"},
        {"label": "Top category", "value": "Shopping", "delta": "₹1,500.00", "delta_style": "up"},
    ]

    transactions = [
        {"date": "2026-01-23", "description": "Weekly grocery shopping", "category": "Food", "category_slug": "food", "amount": "850.00"},
        {"date": "2026-01-20", "description": "Miscellaneous expense", "category": "Other", "category_slug": "other", "amount": "300.00"},
        {"date": "2026-01-17", "description": "Clothing purchase", "category": "Shopping", "category_slug": "shopping", "amount": "1,500.00"},
        {"date": "2026-01-14", "description": "Movie tickets", "category": "Entertainment", "category_slug": "entertainment", "amount": "400.00"},
        {"date": "2026-01-11", "description": "Pharmacy purchase", "category": "Health", "category_slug": "health", "amount": "650.00"},
    ]

    categories = [
        {"name": "Shopping", "slug": "shopping", "total": "1,500.00", "percent": 28},
        {"name": "Bills", "slug": "bills", "total": "1,200.00", "percent": 23},
        {"name": "Food", "slug": "food", "total": "1,100.00", "percent": 21},
        {"name": "Health", "slug": "health", "total": "650.00", "percent": 12},
        {"name": "Entertainment", "slug": "entertainment", "total": "400.00", "percent": 8},
        {"name": "Transport", "slug": "transport", "total": "180.50", "percent": 4},
        {"name": "Other", "slug": "other", "total": "300.00", "percent": 4},
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
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
    with app.app_context():
        init_db()
        seed_db()
    app.run(debug=True, port=5001)
