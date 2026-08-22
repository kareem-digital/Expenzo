from datetime import datetime

from database.db import get_db


def get_user_by_id(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    created_at = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": created_at.strftime("%B %Y"),
    }


def get_summary_stats(user_id, date_from=None, date_to=None):
    conn = get_db()
    date_clause = ""
    params = [user_id]
    if date_from and date_to:
        date_clause = "AND date BETWEEN ? AND ?"
        params += [date_from, date_to]

    try:
        summary = conn.execute(
            f"""
            SELECT COALESCE(SUM(amount), 0) AS total_spent,
                   COUNT(*) AS transaction_count
            FROM expenses
            WHERE user_id = ?
            {date_clause}
            """,
            params,
        ).fetchone()

        top = conn.execute(
            f"""
            SELECT category, SUM(amount) AS category_total
            FROM expenses
            WHERE user_id = ?
            {date_clause}
            GROUP BY category
            ORDER BY category_total DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
    finally:
        conn.close()

    return {
        "total_spent": summary["total_spent"],
        "transaction_count": summary["transaction_count"],
        "top_category": top["category"] if top else "—",
    }


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    conn = get_db()
    date_clause = ""
    params = [user_id]
    if date_from and date_to:
        date_clause = "AND date BETWEEN ? AND ?"
        params += [date_from, date_to]
    params.append(limit)

    try:
        rows = conn.execute(
            f"""
            SELECT date, description, category, amount
            FROM expenses
            WHERE user_id = ?
            {date_clause}
            ORDER BY date DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": row["amount"],
        }
        for row in rows
    ]


def get_category_breakdown(user_id, date_from=None, date_to=None):
    conn = get_db()
    date_clause = ""
    params = [user_id]
    if date_from and date_to:
        date_clause = "AND date BETWEEN ? AND ?"
        params += [date_from, date_to]

    try:
        rows = conn.execute(
            f"""
            SELECT category, SUM(amount) AS amount
            FROM expenses
            WHERE user_id = ?
            {date_clause}
            GROUP BY category
            ORDER BY amount DESC
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    grand_total = sum(row["amount"] for row in rows)
    floored = [int((row["amount"] / grand_total) * 100) for row in rows]
    remainder = 100 - sum(floored)
    floored[0] += remainder

    return [
        {"name": row["category"], "amount": row["amount"], "pct": pct}
        for row, pct in zip(rows, floored)
    ]
