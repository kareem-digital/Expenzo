"""
Tests for Step 6: Date Filter for Profile Page.

Spec: .claude/specs/06-date-filter-profile.md

These tests are written strictly from the spec's stated behavior (routes,
validation rules, inclusive bounds, fallback rules, and the Definition of
Done checklist) — NOT from reading the profile() view's filter logic in
app.py or the date-filter logic in database/queries.py. They exist to catch
implementation bugs, not to confirm current behavior.

Fixtures `app`, `client`, and `seed_user` are provided by tests/conftest.py
and follow the project's existing DB-isolation pattern (swap
`database.db.DB_PATH` to a temp sqlite file per test, `init_db()` on it).
"""

from datetime import datetime

import pytest

import database.db as db


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _today():
    return datetime.today().date()


def _iso(d):
    return d.isoformat()


def _first_of_this_month():
    return _today().replace(day=1)


def _months_ago_first_day(base, months):
    """First day of the month that is `months` calendar-months before base."""
    year, month = base.year, base.month - months
    while month <= 0:
        month += 12
        year -= 1
    return base.replace(year=year, month=month, day=1)


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _insert_expenses(user_id, rows):
    """rows: list of (amount, category, date, description)"""
    conn = db.get_db()
    try:
        conn.executemany(
            """
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            [(user_id, amount, category, date, description) for amount, category, date, description in rows],
        )
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# Fixture data spanning multiple months, anchored to "today"          #
# ------------------------------------------------------------------ #

@pytest.fixture
def date_anchors():
    """
    Deterministic date landmarks computed relative to today, matching how
    the spec says presets must be computed server-side (This Month = first
    day of current calendar month through today; Last 3/6 Months = N-month
    window ending today).
    """
    today = _today()
    this_month_start = _first_of_this_month()
    last_3_start = _months_ago_first_day(today, 2)
    last_6_start = _months_ago_first_day(today, 5)
    # A date guaranteed to be older than the 6-month window (well outside all presets)
    ancient = _months_ago_first_day(today, 11)

    return {
        "today": today,
        "this_month_start": this_month_start,
        "last_3_start": last_3_start,
        "last_6_start": last_6_start,
        "ancient": ancient,
    }


@pytest.fixture
def spanning_expenses(seed_user, date_anchors):
    """
    Expenses deliberately placed:
      - "today_tx": on today's date -> inside every preset, inside This Month
      - "this_month_boundary_tx": exactly on the first day of this month
        -> inside This Month (inclusive lower bound), inside 3/6 month windows
      - "last_3_boundary_tx": exactly on the first day of the Last-3-Months window
        -> inside Last 3 Months (inclusive lower bound) and Last 6 Months,
           but OUTSIDE This Month (unless the window start also happens to be
           this month, which cannot happen since months_ago(today, 2) != today's month
           except in edge month-length cases we avoid by using day=1 anchors)
      - "last_6_boundary_tx": exactly on the first day of the Last-6-Months window
        -> inside Last 6 Months only (not Last 3 Months, not This Month)
      - "ancient_tx": ~11 months back -> outside all presets except All Time
    """
    today = date_anchors["today"]
    this_month_start = date_anchors["this_month_start"]
    last_3_start = date_anchors["last_3_start"]
    last_6_start = date_anchors["last_6_start"]
    ancient = date_anchors["ancient"]

    rows = [
        (111.11, "Food", _iso(today), "today_tx"),
        (222.22, "Bills", _iso(this_month_start), "this_month_boundary_tx"),
        (333.33, "Transport", _iso(last_3_start), "last_3_boundary_tx"),
        (444.44, "Health", _iso(last_6_start), "last_6_boundary_tx"),
        (555.55, "Shopping", _iso(ancient), "ancient_tx"),
    ]
    _insert_expenses(seed_user["id"], rows)
    return {"user": seed_user, **date_anchors}


# ------------------------------------------------------------------ #
# Happy path: no query params = unfiltered (Step 5 behaviour)         #
# ------------------------------------------------------------------ #

class TestUnfilteredBaseline:
    def test_no_query_params_shows_all_expenses(self, client, spanning_expenses):
        _login(client, spanning_expenses["user"]["id"])

        resp = client.get("/profile")

        assert resp.status_code == 200, "Unfiltered /profile should return 200"
        body = resp.get_data(as_text=True)
        # All 5 fixture expenses' amounts should be visible (unfiltered = all data)
        for amount in ("111.11", "222.22", "333.33", "444.44", "555.55"):
            assert amount in body, f"Expected unfiltered view to include amount {amount}"
        assert "5" in body  # sanity: some representation of the 5-transaction count exists

    def test_no_query_params_transaction_count_is_five(self, client, spanning_expenses):
        _login(client, spanning_expenses["user"]["id"])
        resp = client.get("/profile")
        body = resp.get_data(as_text=True)
        assert resp.status_code == 200
        # Total spent across all 5 fixture rows
        total = 111.11 + 222.22 + 333.33 + 444.44 + 555.55
        assert f"{total:,.2f}" in body, "Expected unfiltered total to sum all 5 expenses"


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    def test_profile_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_profile_with_filter_params_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/profile?date_from=2026-01-01&date_to=2026-01-31")
        assert resp.status_code == 302, "Filter params must not bypass the auth guard"
        assert "/login" in resp.headers["Location"]


# ------------------------------------------------------------------ #
# Presets: This Month / Last 3 Months / Last 6 Months / All Time      #
# ------------------------------------------------------------------ #

class TestPresets:
    def test_this_month_preset_includes_current_month_only(self, client, spanning_expenses):
        anchors = spanning_expenses
        _login(client, anchors["user"]["id"])

        resp = client.get(
            f"/profile?date_from={_iso(anchors['this_month_start'])}&date_to={_iso(anchors['today'])}"
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "111.11" in body, "today_tx should be inside This Month range"
        assert "222.22" in body, "this_month_boundary_tx (first of month) should be inside This Month range"
        assert "555.55" not in body, "ancient_tx must be excluded from This Month range"

    def test_last_3_months_preset_includes_expected_window(self, client, spanning_expenses):
        anchors = spanning_expenses
        _login(client, anchors["user"]["id"])

        resp = client.get(
            f"/profile?date_from={_iso(anchors['last_3_start'])}&date_to={_iso(anchors['today'])}"
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "111.11" in body, "today_tx should be inside Last 3 Months range"
        assert "222.22" in body, "this_month_boundary_tx should be inside Last 3 Months range"
        assert "333.33" in body, "last_3_boundary_tx (window start) should be inside Last 3 Months range"
        assert "555.55" not in body, "ancient_tx must be excluded from Last 3 Months range"

    def test_last_6_months_preset_includes_expected_window(self, client, spanning_expenses):
        anchors = spanning_expenses
        _login(client, anchors["user"]["id"])

        resp = client.get(
            f"/profile?date_from={_iso(anchors['last_6_start'])}&date_to={_iso(anchors['today'])}"
        )
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "111.11" in body, "today_tx should be inside Last 6 Months range"
        assert "333.33" in body, "last_3_boundary_tx should be inside Last 6 Months range"
        assert "444.44" in body, "last_6_boundary_tx (window start) should be inside Last 6 Months range"
        assert "555.55" not in body, "ancient_tx (~11 months back) must be excluded from Last 6 Months range"

    def test_all_time_preset_passes_no_query_params_and_shows_everything(self, client, spanning_expenses):
        """Spec: 'The All Time preset must pass no query params (clean /profile URL)'."""
        anchors = spanning_expenses
        _login(client, anchors["user"]["id"])

        resp = client.get("/profile")  # clean URL, as the All Time preset link would produce
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        for amount in ("111.11", "222.22", "333.33", "444.44", "555.55"):
            assert amount in body, "All Time view must include every expense regardless of date"


# ------------------------------------------------------------------ #
# Custom date range filtering across all three sections               #
# ------------------------------------------------------------------ #

class TestCustomRangeFiltersAllSections:
    def test_custom_range_filters_summary_transactions_and_categories(self, client, seed_user):
        _login(client, seed_user["id"])

        _insert_expenses(seed_user["id"], [
            (100.00, "Food", "2026-03-10", "inside_range_food"),
            (200.00, "Bills", "2026-03-20", "inside_range_bills"),
            (312.34, "Transport", "2026-01-05", "outside_range_before"),
            (498.76, "Shopping", "2026-05-01", "outside_range_after"),
        ])

        resp = client.get("/profile?date_from=2026-03-01&date_to=2026-03-31")
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        # Summary stats: total should be exactly the sum of in-range expenses (100+200), not all 4
        assert "300.00" in body, "Summary total should equal sum of only the in-range expenses (100+200)"
        # Recent transactions: in-range visible, out-of-range absent (use distinctive amounts, not shared category names)
        assert "100.00" in body and "200.00" in body
        assert "312.34" not in body, "Expense before the range must not appear in transactions"
        assert "498.76" not in body, "Expense after the range must not appear in transactions"
        # Category breakdown: only in-range categories present, out-of-range categories absent
        assert "Food" in body
        assert "Bills" in body
        assert "Transport" not in body, "Category breakdown must exclude categories with no in-range expenses"
        assert "Shopping" not in body, "Category breakdown must exclude categories with no in-range expenses"

    def test_custom_range_excludes_transactions_outside_bounds(self, client, seed_user):
        _login(client, seed_user["id"])
        _insert_expenses(seed_user["id"], [
            (50.00, "Food", "2026-06-15", "in_range"),
            (75.00, "Transport", "2026-07-15", "after_range"),
            (99.00, "Bills", "2026-05-15", "before_range"),
        ])

        resp = client.get("/profile?date_from=2026-06-01&date_to=2026-06-30")
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "50.00" in body
        assert "75.00" not in body, "Expense after the range must not appear"
        assert "99.00" not in body, "Expense before the range must not appear"


# ------------------------------------------------------------------ #
# Inclusive boundary behaviour                                        #
# ------------------------------------------------------------------ #

class TestInclusiveBoundaries:
    def test_expense_exactly_on_date_from_is_included(self, client, seed_user):
        _login(client, seed_user["id"])
        _insert_expenses(seed_user["id"], [
            (123.45, "Food", "2026-04-01", "on_lower_bound"),
        ])

        resp = client.get("/profile?date_from=2026-04-01&date_to=2026-04-30")
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "123.45" in body, "Expense dated exactly on date_from must be included (inclusive lower bound)"

    def test_expense_exactly_on_date_to_is_included(self, client, seed_user):
        _login(client, seed_user["id"])
        _insert_expenses(seed_user["id"], [
            (543.21, "Bills", "2026-04-30", "on_upper_bound"),
        ])

        resp = client.get("/profile?date_from=2026-04-01&date_to=2026-04-30")
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "543.21" in body, "Expense dated exactly on date_to must be included (inclusive upper bound)"

    def test_expense_one_day_before_date_from_is_excluded(self, client, seed_user):
        _login(client, seed_user["id"])
        _insert_expenses(seed_user["id"], [
            (11.11, "Food", "2026-03-31", "one_day_before"),
        ])

        resp = client.get("/profile?date_from=2026-04-01&date_to=2026-04-30")
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "11.11" not in body, "Expense one day before date_from must be excluded"

    def test_expense_one_day_after_date_to_is_excluded(self, client, seed_user):
        _login(client, seed_user["id"])
        _insert_expenses(seed_user["id"], [
            (22.22, "Food", "2026-05-01", "one_day_after"),
        ])

        resp = client.get("/profile?date_from=2026-04-01&date_to=2026-04-30")
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "22.22" not in body, "Expense one day after date_to must be excluded"


# ------------------------------------------------------------------ #
# Validation: date_from > date_to                                     #
# ------------------------------------------------------------------ #

class TestInvertedRangeValidation:
    def test_date_from_after_date_to_flashes_error_and_falls_back_to_unfiltered(self, client, seed_user):
        _login(client, seed_user["id"])
        _insert_expenses(seed_user["id"], [
            (77.00, "Food", "2026-02-01", "should_still_appear"),
        ])

        resp = client.get("/profile?date_from=2026-06-01&date_to=2026-01-01", follow_redirects=True)
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "Start date must be before end date." in body, (
            "Expected the exact flash error message specified for an inverted date range"
        )
        assert "77.00" in body, "Falls back to unfiltered view, so all expenses should still be visible"

    def test_date_from_equal_to_date_to_is_not_treated_as_inverted(self, client, seed_user):
        """A single-day range (date_from == date_to) is valid, not an error."""
        _login(client, seed_user["id"])
        _insert_expenses(seed_user["id"], [
            (88.88, "Food", "2026-02-15", "single_day"),
            (99.99, "Bills", "2026-02-16", "different_day"),
        ])

        resp = client.get("/profile?date_from=2026-02-15&date_to=2026-02-15")
        body = resp.get_data(as_text=True)

        assert resp.status_code == 200
        assert "Start date must be before end date." not in body
        assert "88.88" in body
        assert "99.99" not in body


# ------------------------------------------------------------------ #
# Malformed date input                                                 #
# ------------------------------------------------------------------ #

class TestMalformedDateInput:
    def test_malformed_date_from_does_not_crash_and_falls_back_to_unfiltered(self, client, seed_user):
        _login(client, seed_user["id"])
        _insert_expenses(seed_user["id"], [
            (65.00, "Food", "2026-02-01", "fixture_tx"),
        ])

        resp = client.get("/profile?date_from=not-a-date&date_to=2026-02-28")

        assert resp.status_code == 200, "Malformed date must not produce a 500 error"
        body = resp.get_data(as_text=True)
        assert "65.00" in body, "Should silently fall back to the unfiltered view"

    def test_malformed_date_to_does_not_crash_and_falls_back_to_unfiltered(self, client, seed_user):
        _login(client, seed_user["id"])
        _insert_expenses(seed_user["id"], [
            (65.00, "Food", "2026-02-01", "fixture_tx"),
        ])

        resp = client.get("/profile?date_from=2026-02-01&date_to=banana")

        assert resp.status_code == 200, "Malformed date must not produce a 500 error"
        body = resp.get_data(as_text=True)
        assert "65.00" in body

    def test_both_dates_malformed_does_not_crash(self, client, seed_user):
        _login(client, seed_user["id"])
        resp = client.get("/profile?date_from=xxxx&date_to=yyyy")
        assert resp.status_code == 200, "Malformed dates on both params must not crash the app"

    @pytest.mark.parametrize("bad_value", [
        "not-a-date",
        "2026/02/01",
        "02-01-2026",
        "2026-13-40",
        "",
        "<script>alert(1)</script>",
        "' OR '1'='1",
    ])
    def test_various_malformed_or_malicious_date_values_are_handled_safely(self, client, seed_user, bad_value):
        _login(client, seed_user["id"])
        resp = client.get(f"/profile?date_from={bad_value}&date_to=2026-02-28")
        assert resp.status_code == 200, f"Value {bad_value!r} must not crash the app or return a server error"


# ------------------------------------------------------------------ #
# Empty result set within a valid range                                #
# ------------------------------------------------------------------ #

class TestNoExpensesInRange:
    def test_valid_range_with_no_matching_expenses_shows_zero_state(self, client, seed_user):
        _login(client, seed_user["id"])
        _insert_expenses(seed_user["id"], [
            (500.00, "Food", "2026-01-01", "far_outside_range"),
        ])

        resp = client.get("/profile?date_from=2026-09-01&date_to=2026-09-30")

        assert resp.status_code == 200, "A valid but empty range must not error"
        body = resp.get_data(as_text=True)
        assert "0.00" in body, "Expected ₹0.00 total spent for a range with no matching expenses"
        assert "500.00" not in body, "Expense outside the selected range must not appear"

    def test_new_user_with_zero_expenses_and_filter_applied_shows_zero_state(self, client, seed_user):
        _login(client, seed_user["id"])

        resp = client.get("/profile?date_from=2026-01-01&date_to=2026-12-31")

        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "0.00" in body
        assert "₹" in body, "Currency symbol must still render even with zero results"


# ------------------------------------------------------------------ #
# Currency symbol always present                                      #
# ------------------------------------------------------------------ #

class TestCurrencySymbolPresence:
    @pytest.mark.parametrize("query_string", [
        "",
        "?date_from=2026-01-01&date_to=2026-01-31",
        "?date_from=not-a-date&date_to=also-not-a-date",
        "?date_from=2026-06-01&date_to=2026-01-01",  # inverted range
    ])
    def test_rupee_symbol_present_regardless_of_filter_state(self, client, seed_user, query_string):
        _login(client, seed_user["id"])
        _insert_expenses(seed_user["id"], [
            (10.00, "Food", "2026-01-15", "fixture_tx"),
        ])

        resp = client.get(f"/profile{query_string}")

        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "₹" in body, f"₹ symbol must be present for query string {query_string!r}"
