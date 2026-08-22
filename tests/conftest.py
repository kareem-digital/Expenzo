import os
import tempfile

import pytest
from werkzeug.security import generate_password_hash

import database.db as db
from app import app as flask_app


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    original_db_path = db.DB_PATH
    db.DB_PATH = db_path

    db.init_db()

    flask_app.config.update(TESTING=True, SECRET_KEY="test-secret-key")

    yield flask_app

    db.DB_PATH = original_db_path
    os.close(db_fd)
    os.remove(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seed_user(app):
    conn = db.get_db()
    try:
        password_hash = generate_password_hash("testpass123")
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Test User", "test@example.com", password_hash),
        )
        conn.commit()
        user_id = cursor.lastrowid
    finally:
        conn.close()

    return {"id": user_id, "email": "test@example.com", "password": "testpass123"}


@pytest.fixture
def seed_rounding_expenses(seed_user):
    conn = db.get_db()
    try:
        rows = [
            (seed_user["id"], 33.34, "Alpha", "2026-08-01", "x"),
            (seed_user["id"], 33.33, "Beta", "2026-08-02", "x"),
            (seed_user["id"], 33.33, "Gamma", "2026-08-03", "x"),
        ]
        conn.executemany(
            """
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()

    return seed_user


@pytest.fixture
def seed_expenses(seed_user):
    conn = db.get_db()
    try:
        rows = [
            (seed_user["id"], 100.00, "Food", "2026-08-01", "Groceries"),
            (seed_user["id"], 50.00, "Food", "2026-08-05", "Snacks"),
            (seed_user["id"], 200.00, "Bills", "2026-08-10", "Electricity"),
            (seed_user["id"], 150.00, "Transport", "2026-08-15", "Cab fares"),
        ]
        conn.executemany(
            """
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()

    return seed_user
