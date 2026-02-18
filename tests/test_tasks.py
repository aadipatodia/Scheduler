"""
Test file for task-related endpoints, auth, and multi-user isolation.
Uses phone-number-based auth with cookie sessions.
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.database import get_db, Base

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ==================== HELPERS ====================

def make_client():
    """Return a fresh TestClient whose cookie jar is empty."""
    return TestClient(app)


def login(c: TestClient, phone="+1234567890"):
    """Log in (or auto-create) a user via phone number. Session cookie stored in c."""
    res = c.post("/auth/login", json={"phone": phone})
    assert res.status_code == 200, res.text
    return res.json()


# ==================== AUTH TESTS ====================

def test_login_creates_user():
    c = make_client()
    user = login(c)
    assert user["phone"] == "+1234567890"

    me = c.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["phone"] == "+1234567890"


def test_login_same_phone_returns_same_user():
    c1 = make_client()
    u1 = login(c1)

    c2 = make_client()
    u2 = login(c2)

    assert u1["id"] == u2["id"]


def test_unauthenticated_access_rejected():
    c = make_client()
    res = c.get("/goals")
    assert res.status_code == 401


def test_logout_clears_session():
    c = make_client()
    login(c)
    assert c.get("/auth/me").status_code == 200
    c.post("/auth/logout")
    assert c.get("/auth/me").status_code == 401


# ==================== TASK TESTS ====================

def test_create_task():
    c = make_client()
    login(c)

    res = c.post("/tasks", json={
        "title": "Test Task", "description": "This is a test task",
        "category": "daily", "priority": 3, "scheduled_date": datetime.utcnow().isoformat(),
    })
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Test Task"
    assert data["priority"] == 3
    assert data["status"] == 0


def test_get_today_tasks():
    c = make_client()
    login(c)
    c.post("/tasks", json={
        "title": "Today's Task", "category": "daily", "priority": 2,
        "scheduled_date": datetime.utcnow().isoformat(),
    })
    res = c.get("/tasks/today")
    assert res.status_code == 200
    assert res.json()["total"] >= 1


def test_update_task_status():
    c = make_client()
    login(c)
    task_id = c.post("/tasks", json={
        "title": "Task to Complete", "category": "daily", "priority": 1,
        "scheduled_date": datetime.utcnow().isoformat(),
    }).json()["id"]

    res = c.put(f"/tasks/{task_id}", json={"status": 1, "reason": "Task finished"})
    assert res.status_code == 200
    assert res.json()["status"] == 1
    assert res.json()["completed_date"] is not None


def test_delete_task():
    c = make_client()
    login(c)
    task_id = c.post("/tasks", json={"title": "Task to Delete", "category": "daily", "priority": 1}).json()["id"]
    res = c.delete(f"/tasks/{task_id}")
    assert res.status_code == 200


# ==================== GOAL TESTS ====================

def test_create_goal():
    c = make_client()
    login(c)
    res = c.post("/goals", json={
        "title": "Become an ML Engineer",
        "description": "Learn machine learning and get a job",
        "target_date": (datetime.utcnow() + timedelta(days=210)).isoformat(),
    })
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Become an ML Engineer"
    assert data["status"] == "active"


def test_list_goals():
    c = make_client()
    login(c)
    for i in range(3):
        c.post("/goals", json={"title": f"Goal {i+1}", "description": f"Desc {i+1}"})
    res = c.get("/goals")
    assert res.status_code == 200
    assert len(res.json()) == 3


def test_health_check():
    c = make_client()
    res = c.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_stats_overview():
    c = make_client()
    login(c)
    c.post("/goals", json={"title": "Test Goal", "description": "A goal"})
    c.post("/tasks", json={"title": "Test Task", "category": "daily", "priority": 1})
    res = c.get("/stats/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["goals"]["total"] >= 1
    assert data["tasks"]["total"] >= 1


# ==================== MULTI-USER ISOLATION ====================

def test_users_cannot_see_each_others_goals():
    alice = make_client()
    login(alice, "+1111111111")
    bob = make_client()
    login(bob, "+2222222222")

    alice.post("/goals", json={"title": "Alice Goal"})
    bob.post("/goals", json={"title": "Bob Goal"})

    ag = alice.get("/goals").json()
    bg = bob.get("/goals").json()
    assert len(ag) == 1 and ag[0]["title"] == "Alice Goal"
    assert len(bg) == 1 and bg[0]["title"] == "Bob Goal"


def test_users_cannot_see_each_others_tasks():
    alice = make_client()
    login(alice, "+1111111111")
    bob = make_client()
    login(bob, "+2222222222")

    alice.post("/tasks", json={"title": "Alice Task", "category": "daily", "priority": 1, "scheduled_date": datetime.utcnow().isoformat()})
    bob.post("/tasks", json={"title": "Bob Task", "category": "daily", "priority": 1, "scheduled_date": datetime.utcnow().isoformat()})

    at = alice.get("/tasks").json()
    bt = bob.get("/tasks").json()
    assert len(at) == 1 and at[0]["title"] == "Alice Task"
    assert len(bt) == 1 and bt[0]["title"] == "Bob Task"


def test_user_cannot_access_others_goal():
    alice = make_client()
    login(alice, "+1111111111")
    bob = make_client()
    login(bob, "+2222222222")

    goal_id = alice.post("/goals", json={"title": "Alice Goal"}).json()["id"]
    assert bob.get(f"/goals/{goal_id}").status_code == 404


def test_user_cannot_delete_others_goal():
    alice = make_client()
    login(alice, "+1111111111")
    bob = make_client()
    login(bob, "+2222222222")

    goal_id = alice.post("/goals", json={"title": "Alice Goal"}).json()["id"]
    assert bob.delete(f"/goals/{goal_id}").status_code == 404


def test_user_cannot_update_others_task():
    alice = make_client()
    login(alice, "+1111111111")
    bob = make_client()
    login(bob, "+2222222222")

    task_id = alice.post("/tasks", json={"title": "Alice Task", "category": "daily", "priority": 1}).json()["id"]
    assert bob.put(f"/tasks/{task_id}", json={"status": 1}).status_code == 404


def test_stats_are_user_scoped():
    alice = make_client()
    login(alice, "+1111111111")
    bob = make_client()
    login(bob, "+2222222222")

    for _ in range(3):
        alice.post("/goals", json={"title": "Alice G"})
    bob.post("/goals", json={"title": "Bob G"})

    assert alice.get("/stats/overview").json()["goals"]["total"] == 3
    assert bob.get("/stats/overview").json()["goals"]["total"] == 1
