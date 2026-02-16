"""
Test file for task-related endpoints and functionality
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.database import get_db, Base
from src.models import Goal, Task

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test and drop after"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_create_task():
    """Test creating a new task"""
    task_data = {
        "title": "Test Task",
        "description": "This is a test task",
        "category": "daily",
        "priority": 3,
        "scheduled_date": datetime.utcnow().isoformat()
    }
    
    response = client.post("/tasks", json=task_data)
    assert response.status_code == 201
    
    data = response.json()
    assert data["title"] == "Test Task"
    assert data["priority"] == 3
    assert data["status"] == 0  # DUE


def test_get_today_tasks():
    """Test retrieving today's tasks"""
    # Create a task for today
    today = datetime.utcnow()
    task_data = {
        "title": "Today's Task",
        "description": "Task for today",
        "category": "daily",
        "priority": 2,
        "scheduled_date": today.isoformat()
    }
    
    client.post("/tasks", json=task_data)
    
    # Retrieve today's tasks
    response = client.get("/tasks/today")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total"] >= 1
    assert len(data["tasks"]) >= 1


def test_update_task_status():
    """Test updating a task's status"""
    # Create a task
    task_data = {
        "title": "Task to Complete",
        "description": "This task will be completed",
        "category": "daily",
        "priority": 1,
        "scheduled_date": datetime.utcnow().isoformat()
    }
    
    create_response = client.post("/tasks", json=task_data)
    task_id = create_response.json()["id"]
    
    # Update status to completed
    update_data = {
        "status": 1,  # COMPLETED
        "reason": "Task finished"
    }
    
    response = client.put(f"/tasks/{task_id}", json=update_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == 1
    assert data["completed_date"] is not None


def test_delete_task():
    """Test deleting a task"""
    # Create a task
    task_data = {
        "title": "Task to Delete",
        "category": "daily",
        "priority": 1
    }
    
    create_response = client.post("/tasks", json=task_data)
    task_id = create_response.json()["id"]
    
    # Delete the task
    response = client.delete(f"/tasks/{task_id}")
    assert response.status_code == 200
    
    # Verify it's deleted (would need additional endpoint to verify)


def test_create_goal():
    """Test creating a goal"""
    goal_data = {
        "title": "Become an ML Engineer",
        "description": "Learn machine learning and get a job",
        "target_date": (datetime.utcnow() + timedelta(days=210)).isoformat()
    }
    
    response = client.post("/goals", json=goal_data)
    assert response.status_code == 201
    
    data = response.json()
    assert data["title"] == "Become an ML Engineer"
    assert data["status"] == "active"


def test_list_goals():
    """Test listing all goals"""
    # Create a few goals
    for i in range(3):
        goal_data = {
            "title": f"Goal {i+1}",
            "description": f"Description for goal {i+1}"
        }
        client.post("/goals", json=goal_data)
    
    # List goals
    response = client.get("/goals")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 3


def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"


def test_stats_overview():
    """Test statistics endpoint"""
    # Create some test data
    goal_data = {
        "title": "Test Goal",
        "description": "A goal for testing"
    }
    client.post("/goals", json=goal_data)
    
    task_data = {
        "title": "Test Task",
        "category": "daily",
        "priority": 1
    }
    client.post("/tasks", json=task_data)
    
    # Get stats
    response = client.get("/stats/overview")
    assert response.status_code == 200
    
    data = response.json()
    assert "goals" in data
    assert "tasks" in data
    assert data["goals"]["total"] >= 1
    assert data["tasks"]["total"] >= 1