#!/usr/bin/env python3
"""
Example script demonstrating AI-Scheduler API usage

This script shows you how to:
1. Create a goal
2. Generate a roadmap
3. Create tasks
4. Update task status
"""

import requests
import json
from datetime import datetime, timedelta

# API base URL
BASE_URL = "http://localhost:8000"


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def create_goal(title, description, months_from_now=6):
    """Create a new goal"""
    print_section("Creating a Goal")
    
    target_date = datetime.utcnow() + timedelta(days=30 * months_from_now)
    
    data = {
        "title": title,
        "description": description,
        "target_date": target_date.isoformat() + "Z"
    }
    
    response = requests.post(f"{BASE_URL}/goals", json=data)
    
    if response.status_code == 201:
        goal = response.json()
        print(f"✓ Goal created successfully!")
        print(f"  ID: {goal['id']}")
        print(f"  Title: {goal['title']}")
        print(f"  Target Date: {goal['target_date']}")
        return goal['id']
    else:
        print(f"✗ Error: {response.status_code}")
        print(response.text)
        return None


def generate_roadmap(goal_id, context=None):
    """Generate AI roadmap for a goal"""
    print_section("Generating AI Roadmap with Gemini")
    
    print("Asking Gemini to create a roadmap... (this may take a moment)")
    
    params = {}
    if context:
        params['context'] = context
    
    response = requests.post(f"{BASE_URL}/goals/{goal_id}/roadmap", json=params)
    
    if response.status_code == 200:
        roadmap = response.json()
        print(f"✓ Roadmap generated successfully!")
        print(f"\nRoadmap Preview:")
        print("-" * 60)
        # Print first 500 characters
        print(roadmap['roadmap_text'][:500] + "...")
        print("-" * 60)
        return roadmap['id']
    else:
        print(f"✗ Error: {response.status_code}")
        print(response.text)
        return None


def create_task(title, description, priority=3):
    """Create a daily task"""
    print(f"\nCreating task: {title}")
    
    # Schedule for tomorrow
    scheduled_date = datetime.utcnow() + timedelta(days=1)
    
    data = {
        "title": title,
        "description": description,
        "category": "daily",
        "priority": priority,
        "scheduled_date": scheduled_date.isoformat() + "Z"
    }
    
    response = requests.post(f"{BASE_URL}/tasks", json=data)
    
    if response.status_code == 201:
        task = response.json()
        print(f"  ✓ Task created (ID: {task['id']})")
        return task['id']
    else:
        print(f"  ✗ Error: {response.status_code}")
        return None


def list_tasks_today():
    """List all tasks for today"""
    print_section("Today's Tasks")
    
    response = requests.get(f"{BASE_URL}/tasks/today")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Total tasks: {data['total']}")
        print(f"  Completed: {data['completed']}")
        print(f"  Due: {data['due']}")
        print(f"  Missed: {data['missed']}")
        
        if data['tasks']:
            print("\nTask List:")
            for task in data['tasks']:
                status = "✓" if task['status'] == 1 else "○"
                print(f"  {status} [{task['priority']}] {task['title']}")
    else:
        print(f"✗ Error: {response.status_code}")


def complete_task(task_id):
    """Mark a task as completed"""
    print(f"\nMarking task {task_id} as completed...")
    
    data = {
        "status": 1,
        "reason": "Completed via example script"
    }
    
    response = requests.put(f"{BASE_URL}/tasks/{task_id}", json=data)
    
    if response.status_code == 200:
        print("  ✓ Task completed!")
    else:
        print(f"  ✗ Error: {response.status_code}")


def get_stats():
    """Get overall statistics"""
    print_section("Statistics Overview")
    
    response = requests.get(f"{BASE_URL}/stats/overview")
    
    if response.status_code == 200:
        stats = response.json()
        print("Goals:")
        print(f"  Total: {stats['goals']['total']}")
        print(f"  Active: {stats['goals']['active']}")
        print("\nTasks:")
        print(f"  Total: {stats['tasks']['total']}")
        print(f"  Completed: {stats['tasks']['completed']}")
        print(f"  Missed: {stats['tasks']['missed']}")
        print(f"  Completion Rate: {stats['tasks']['completion_rate']}%")
    else:
        print(f"✗ Error: {response.status_code}")


def main():
    """Main example workflow"""
    print("\n" + "=" * 60)
    print("  AI-Scheduler API Example (Using Gemini)")
    print("=" * 60)
    print("\nThis script demonstrates the basic API workflow.")
    print("Make sure the server is running at http://localhost:8000")
    
    input("\nPress Enter to continue...")
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            print("✗ Server health check failed!")
            return
        print("✓ Server is running\n")
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server. Is it running?")
        print("  Start it with: uvicorn src.main:app --reload")
        return
    
    # Example workflow
    
    # 1. Create a goal
    goal_id = create_goal(
        title="Become a Machine Learning Engineer",
        description="Learn ML fundamentals and build a portfolio in 6 months",
        months_from_now=6
    )
    
    if not goal_id:
        print("Failed to create goal. Exiting.")
        return
    
    input("\nPress Enter to generate roadmap with Gemini...")
    
    # 2. Generate roadmap
    roadmap_id = generate_roadmap(
        goal_id,
        context="I have Python basics but no ML experience. I can dedicate 2 hours daily."
    )
    
    if not roadmap_id:
        print("Failed to generate roadmap. Continuing anyway...")
    
    input("\nPress Enter to create sample tasks...")
    
    # 3. Create some example tasks
    print_section("Creating Sample Tasks")
    
    tasks = [
        ("Complete Python refresher course", "Review Python basics for ML", 4),
        ("Set up ML development environment", "Install Jupyter, NumPy, Pandas, Scikit-learn", 5),
        ("Read 'Hands-On ML' Chapter 1", "Introduction to Machine Learning", 3),
        ("Practice: Linear Regression tutorial", "Complete kaggle tutorial on linear regression", 4),
    ]
    
    task_ids = []
    for title, desc, priority in tasks:
        task_id = create_task(title, desc, priority)
        if task_id:
            task_ids.append(task_id)
    
    input("\nPress Enter to view today's tasks...")
    
    # 4. List today's tasks
    list_tasks_today()
    
    input("\nPress Enter to complete a task...")
    
    # 5. Complete one task
    if task_ids:
        complete_task(task_ids[0])
    
    input("\nPress Enter to view statistics...")
    
    # 6. Get statistics
    get_stats()
    
    print_section("Example Complete!")
    print("You can now:")
    print("  • View API docs: http://localhost:8000/docs")
    print("  • Check your data in the database")
    print("  • Explore other API endpoints")
    print("  • Build your own integrations!")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExample interrupted by user.")
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")