import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.main import create_app
from app.models import db


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    app = create_app()
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
        from app.seed import seed_database
        seed_database()
    with app.test_client() as c:
        yield c


def _token(client, email, password):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.get_json()["access_token"]


def test_health(client):
    assert client.get("/api/v1/health").get_json()["status"] == "ok"


def test_login_and_dashboard(client):
    token = _token(client, "admin@projectace.local", "admin123")
    r = client.get("/api/v1/dashboard/stats", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "total_tasks" in r.get_json()


def test_kanban_move(client):
    admin = _token(client, "admin@projectace.local", "admin123")
    board = client.get("/api/v1/projects/1/board", headers={"Authorization": f"Bearer {admin}"}).get_json()
    for col in ("TODO", "IN_PROGRESS", "DONE"):
        if board.get(col):
            task_id = board[col][0]["id"]
            break
    else:
        pytest.skip("no tasks in seed")
    r = client.patch(f"/api/v1/tasks/{task_id}/move",
                     json={"status": "DONE", "position": 0},
                     headers={"Authorization": f"Bearer {admin}"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "DONE"
