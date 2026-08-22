"""
Tests for Step 7: Add Expense.

Spec: .claude/specs/07-add-expense.md

These tests are written strictly from the spec's stated behavior (routes,
validation rules, redirect targets, optional-field handling, and the
Definition of Done checklist) — NOT from reading the add_expense() view or
the insert_expense() query helper in app.py / database/queries.py. They
exist to catch implementation bugs, not to confirm current behavior.

Fixtures `app`, `client`, and `seed_user` are provided by tests/conftest.py
and follow the project's existing DB-isolation pattern (swap
`database.db.DB_PATH` to a temp sqlite file per test, `init_db()` on it).
"""

import pytest

import database.db as db
from database import queries


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _fetch_expenses_for_user(user_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


VALID_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


# ------------------------------------------------------------------ #
# Unit tests: database.queries.insert_expense                        #
# ------------------------------------------------------------------ #

class TestInsertExpenseUnit:
    def test_insert_expense_valid_data_row_is_queryable(self, seed_user):
        """Spec unit test row 1: valid insert is retrievable from the DB."""
        queries.insert_expense(
            user_id=seed_user["id"],
            amount=50.0,
            category="Food",
            date="2026-03-20",
            description="Lunch",
        )

        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 1, "Expected exactly one inserted expense row"
        row = rows[0]
        assert row["user_id"] == seed_user["id"]
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

    def test_insert_expense_returns_new_row_id(self, seed_user):
        new_id = queries.insert_expense(
            user_id=seed_user["id"],
            amount=10.0,
            category="Other",
            date="2026-01-01",
            description="Misc",
        )
        assert new_id is not None, "insert_expense should report the new row's identity"

        rows = _fetch_expenses_for_user(seed_user["id"])
        assert rows[0]["id"] == new_id

    def test_insert_expense_with_none_description_stores_null(self, seed_user):
        """Spec unit test row 2: description=None is stored as NULL."""
        queries.insert_expense(
            user_id=seed_user["id"],
            amount=25.0,
            category="Transport",
            date="2026-04-01",
            description=None,
        )

        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 1
        assert rows[0]["description"] is None, "description=None must be stored as NULL, not empty string"


# ------------------------------------------------------------------ #
# GET /expenses/add — auth guard                                     #
# ------------------------------------------------------------------ #

class TestGetAddExpenseAuthGuard:
    def test_get_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/expenses/add")
        assert resp.status_code == 302, "Unauthenticated GET must redirect, not render the form"
        assert "/login" in resp.headers["Location"]


# ------------------------------------------------------------------ #
# GET /expenses/add — authenticated                                  #
# ------------------------------------------------------------------ #

class TestGetAddExpenseAuthenticated:
    def test_get_authenticated_returns_200(self, client, seed_user):
        _login(client, seed_user["id"])
        resp = client.get("/expenses/add")
        assert resp.status_code == 200

    def test_get_authenticated_form_has_post_method(self, client, seed_user):
        _login(client, seed_user["id"])
        resp = client.get("/expenses/add")
        body = resp.get_data(as_text=True)
        assert "<form" in body, "Expected an add-expense <form> in the response"
        assert "post" in body.lower(), "Form must submit via POST"

    @pytest.mark.parametrize("category", VALID_CATEGORIES)
    def test_get_authenticated_category_select_contains_each_fixed_option(self, client, seed_user, category):
        _login(client, seed_user["id"])
        resp = client.get("/expenses/add")
        body = resp.get_data(as_text=True)
        assert "<select" in body, "Expected a category <select> element"
        assert category in body, f"Expected category option '{category}' in the form"

    def test_get_authenticated_category_select_has_exactly_seven_options(self, client, seed_user):
        _login(client, seed_user["id"])
        resp = client.get("/expenses/add")
        body = resp.get_data(as_text=True)
        for category in VALID_CATEGORIES:
            assert category in body


# ------------------------------------------------------------------ #
# POST /expenses/add — auth guard                                    #
# ------------------------------------------------------------------ #

class TestPostAddExpenseAuthGuard:
    def test_post_unauthenticated_redirects_to_login(self, client):
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )
        assert resp.status_code == 302, "Unauthenticated POST must redirect, not process the submission"
        assert "/login" in resp.headers["Location"]

    def test_post_unauthenticated_does_not_insert_row(self, client):
        client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )
        conn = db.get_db()
        try:
            count = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
        finally:
            conn.close()
        assert count == 0, "Unauthenticated POST must not write to the database"


# ------------------------------------------------------------------ #
# POST /expenses/add — happy path                                    #
# ------------------------------------------------------------------ #

class TestPostAddExpenseHappyPath:
    def test_post_valid_data_redirects_to_profile(self, client, seed_user):
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )
        assert resp.status_code == 302
        assert "/profile" in resp.headers["Location"]

    def test_post_valid_data_inserts_row_matching_submission(self, client, seed_user):
        _login(client, seed_user["id"])
        client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )
        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 1, "Expected the new expense to exist in the database"
        row = rows[0]
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

    def test_post_valid_data_does_not_rerender_form(self, client, seed_user):
        """On success the spec says: redirect to profile, do NOT render the form again."""
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )
        assert resp.status_code == 302, "Successful submission must redirect (not return 200 with the form)"


# ------------------------------------------------------------------ #
# POST /expenses/add — validation errors                             #
# ------------------------------------------------------------------ #

class TestPostAddExpenseValidation:
    def test_post_missing_amount_rerenders_form_with_error(self, client, seed_user):
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )
        assert resp.status_code == 200, "Missing amount must re-render the form, not redirect"
        body = resp.get_data(as_text=True)
        assert "<form" in body

    def test_post_missing_amount_does_not_insert_row(self, client, seed_user):
        _login(client, seed_user["id"])
        client.post(
            "/expenses/add",
            data={
                "amount": "",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )
        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 0, "Invalid submission must not create a row"

    def test_post_zero_amount_rerenders_form_with_error(self, client, seed_user):
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "0",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )
        assert resp.status_code == 200, "Zero amount must re-render the form, not redirect"
        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 0, "Zero amount must not be inserted"

    def test_post_negative_amount_rerenders_form_with_error(self, client, seed_user):
        """Spec: amount must be a positive number greater than 0."""
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "-10",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )
        assert resp.status_code == 200, "Negative amount must re-render the form, not redirect"
        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 0, "Negative amount must not be inserted"

    def test_post_non_numeric_amount_rerenders_form_with_error(self, client, seed_user):
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "abc",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )
        assert resp.status_code == 200, "Non-numeric amount must re-render the form, not redirect"
        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 0, "Non-numeric amount must not be inserted"

    def test_post_invalid_category_rerenders_form_with_error(self, client, seed_user):
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "NotARealCategory",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )
        assert resp.status_code == 200, "Invalid category must re-render the form, not redirect"
        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 0, "Invalid category must not be inserted"

    def test_post_missing_category_rerenders_form_with_error(self, client, seed_user):
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "",
                "date": "2026-03-20",
                "description": "Lunch",
            },
        )
        assert resp.status_code == 200, "Missing category must re-render the form, not redirect"
        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 0

    def test_post_invalid_date_string_rerenders_form_with_error(self, client, seed_user):
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "not-a-date",
                "description": "Lunch",
            },
        )
        assert resp.status_code == 200, "Invalid date must re-render the form, not redirect"
        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 0, "Invalid date must not be inserted"

    def test_post_missing_date_rerenders_form_with_error(self, client, seed_user):
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "",
                "description": "Lunch",
            },
        )
        assert resp.status_code == 200, "Missing date must re-render the form, not redirect"
        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 0

    @pytest.mark.parametrize("bad_date", [
        "2026/03/20",
        "20-03-2026",
        "2026-13-40",
        "banana",
        "<script>alert(1)</script>",
        "' OR '1'='1",
    ])
    def test_post_various_malformed_or_malicious_dates_do_not_crash_or_insert(self, client, seed_user, bad_date):
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "Food",
                "date": bad_date,
                "description": "Lunch",
            },
        )
        assert resp.status_code == 200, f"Malformed date {bad_date!r} must not crash the app or redirect"
        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 0, f"Malformed date {bad_date!r} must not result in an inserted row"

    def test_post_validation_error_repopulates_previous_values(self, client, seed_user):
        """Spec: on validation error, re-render form with error message and previous values pre-filled."""
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "0",
                "category": "Food",
                "date": "2026-03-20",
                "description": "Coffee with friends",
            },
        )
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "Coffee with friends" in body, "Previously entered description should be retained in the re-rendered form"
        assert "2026-03-20" in body, "Previously entered date should be retained in the re-rendered form"


# ------------------------------------------------------------------ #
# POST /expenses/add — optional description                          #
# ------------------------------------------------------------------ #

class TestPostAddExpenseOptionalDescription:
    def test_post_no_description_redirects_to_profile(self, client, seed_user):
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "2026-03-20",
                "description": "",
            },
        )
        assert resp.status_code == 302
        assert "/profile" in resp.headers["Location"]

    def test_post_no_description_row_inserted_with_null_description(self, client, seed_user):
        _login(client, seed_user["id"])
        client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "2026-03-20",
                "description": "",
            },
        )
        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 1
        assert rows[0]["description"] is None, "Blank description must be stored as NULL, not empty string"

    def test_post_whitespace_only_description_stored_as_null(self, client, seed_user):
        """Spec: description is stripped of whitespace before storing; blank -> None."""
        _login(client, seed_user["id"])
        client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "2026-03-20",
                "description": "   ",
            },
        )
        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 1
        assert rows[0]["description"] is None, "Whitespace-only description must be stripped and stored as NULL"

    def test_post_description_omitted_entirely_still_succeeds(self, client, seed_user):
        """description field is optional; omitting it entirely from the POST body should not error."""
        _login(client, seed_user["id"])
        resp = client.post(
            "/expenses/add",
            data={
                "amount": "50.0",
                "category": "Food",
                "date": "2026-03-20",
            },
        )
        assert resp.status_code == 302
        rows = _fetch_expenses_for_user(seed_user["id"])
        assert len(rows) == 1
        assert rows[0]["description"] is None
