import sqlite3
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, abort, session
from werkzeug.security import check_password_hash

from database.db import init_db, seed_db, create_user, get_user_by_email, get_user_by_id
from database import queries as profile_queries

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"


@app.context_processor
def inject_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return {"current_user": None}
    return {"current_user": get_user_by_id(user_id)}


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
# Profile filter helpers                                              #
# ------------------------------------------------------------------ #

def _preset_ranges():
    today = datetime.today().date()
    this_month_start = today.replace(day=1)

    def months_ago(base, months):
        year, month = base.year, base.month - months
        while month <= 0:
            month += 12
            year -= 1
        return base.replace(year=year, month=month, day=1)

    return {
        "this_month": (this_month_start.isoformat(), today.isoformat()),
        "last_3_months": (months_ago(today, 2).isoformat(), today.isoformat()),
        "last_6_months": (months_ago(today, 5).isoformat(), today.isoformat()),
        "all_time": (None, None),
    }


def _parse_date(value):
    if not value:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    return value


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    profile_user = profile_queries.get_user_by_id(user_id)
    if profile_user is None:
        session.clear()
        return redirect(url_for("login"))

    initials = "".join(part[0].upper() for part in profile_user["name"].split()[:2])
    user = {
        "name": profile_user["name"],
        "email": profile_user["email"],
        "initials": initials,
        "member_since": profile_user["member_since"],
    }

    date_from = _parse_date(request.args.get("date_from"))
    date_to = _parse_date(request.args.get("date_to"))

    if date_from and date_to and date_from > date_to:
        flash("Start date must be before end date.", "error")
        date_from = None
        date_to = None

    presets = _preset_ranges()
    if date_from is None and date_to is None:
        active_preset = "all_time"
    else:
        active_preset = "custom"
        for name, (preset_from, preset_to) in presets.items():
            if name != "all_time" and (preset_from, preset_to) == (date_from, date_to):
                active_preset = name
                break

    summary = profile_queries.get_summary_stats(user_id, date_from=date_from, date_to=date_to)
    stats = [
        {"label": "Total spent", "value": f"₹{summary['total_spent']:,.2f}"},
        {"label": "Transactions", "value": str(summary["transaction_count"])},
        {"label": "Top category", "value": summary["top_category"]},
    ]

    transactions = [
        {
            "date": tx["date"],
            "description": tx["description"],
            "category": tx["category"],
            "category_slug": tx["category"].lower(),
            "amount": f"{tx['amount']:,.2f}",
        }
        for tx in profile_queries.get_recent_transactions(user_id, limit=10, date_from=date_from, date_to=date_to)
    ]

    categories = [
        {
            "name": cat["name"],
            "slug": cat["name"].lower(),
            "total": f"{cat['amount']:,.2f}",
            "percent": cat["pct"],
        }
        for cat in profile_queries.get_category_breakdown(user_id, date_from=date_from, date_to=date_to)
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        active_preset=active_preset,
        date_from=date_from,
        date_to=date_to,
        presets=presets,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


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
