from database import queries


def test_get_user_by_id_returns_profile_fields(seed_user):
    result = queries.get_user_by_id(seed_user["id"])
    assert result["name"] == "Test User"
    assert result["email"] == "test@example.com"
    assert result["member_since"]


def test_get_user_by_id_nonexistent_returns_none(app):
    assert queries.get_user_by_id(999999) is None


def test_get_summary_stats_with_expenses(seed_expenses):
    stats = queries.get_summary_stats(seed_expenses["id"])
    assert stats["total_spent"] == 500.00
    assert stats["transaction_count"] == 4
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_no_expenses(seed_user):
    stats = queries.get_summary_stats(seed_user["id"])
    assert stats["total_spent"] == 0
    assert stats["transaction_count"] == 0
    assert stats["top_category"] == "—"


def test_get_recent_transactions_ordering(seed_expenses):
    txs = queries.get_recent_transactions(seed_expenses["id"])
    assert len(txs) == 4
    dates = [t["date"] for t in txs]
    assert dates == sorted(dates, reverse=True)
    assert txs[0]["date"] == "2026-08-15"
    assert set(txs[0].keys()) == {"date", "description", "category", "amount"}


def test_get_recent_transactions_empty(seed_user):
    assert queries.get_recent_transactions(seed_user["id"]) == []


def test_get_category_breakdown_with_expenses(seed_expenses):
    breakdown = queries.get_category_breakdown(seed_expenses["id"])
    assert sum(item["pct"] for item in breakdown) == 100
    assert all(isinstance(item["pct"], int) for item in breakdown)
    amounts = [item["amount"] for item in breakdown]
    assert amounts == sorted(amounts, reverse=True)
    names = [item["name"] for item in breakdown]
    assert set(names) == {"Food", "Bills", "Transport"}


def test_get_category_breakdown_empty(seed_user):
    assert queries.get_category_breakdown(seed_user["id"]) == []


def test_get_category_breakdown_rounding_remainder(seed_rounding_expenses):
    breakdown = queries.get_category_breakdown(seed_rounding_expenses["id"])
    assert sum(item["pct"] for item in breakdown) == 100
    pcts = [item["pct"] for item in breakdown]
    assert pcts[0] == 34
    assert pcts[1] == 33
    assert pcts[2] == 33


def test_profile_unauthenticated_redirects(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_authenticated_shows_seed_data(client):
    import database.db as db

    db.seed_db()
    seed_user = db.get_user_by_email("demo@expenzo.com")

    with client.session_transaction() as sess:
        sess["user_id"] = seed_user["id"]

    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Demo User" in body
    assert "demo@expenzo.com" in body
    assert "₹" in body
    assert "5,330.50" in body
    assert "Shopping" in body


def test_profile_new_user_shows_zero_state(client, seed_user):
    with client.session_transaction() as sess:
        sess["user_id"] = seed_user["id"]

    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "0.00" in body
