"""
Main FastAPI application for AI-Scheduler
"""
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import uvicorn
import os

from .database import get_db, init_db
from .models import Goal, Roadmap, Milestone, Task, AuditLog, TaskStatus
from .services.gemini_service import GeminiService
from .schemas import (
    GoalCreate, GoalResponse, RoadmapCreate, RoadmapResponse,
    TaskCreate, TaskResponse, TaskUpdate, DailyTasksResponse
)

# Initialize FastAPI app
app = FastAPI(
    title="AI-Scheduler API",
    description="Intelligent task scheduling with AI-powered planning",
    version="1.0.0"
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini service
gemini_service = GeminiService()


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()
    print("AI-Scheduler API started successfully!")
    print("Frontend available at: http://localhost:8000")
    print("API docs available at: http://localhost:8000/docs")


# ==================== FRONTEND ROUTE ====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the frontend"""
    return templates.TemplateResponse("index.html", {"request": request})


# ==================== API ROUTES ====================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}


# ==================== GOAL ENDPOINTS ====================

@app.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    goal_data: GoalCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new long-term goal
    """
    goal = Goal(
        title=goal_data.title,
        description=goal_data.description,
        target_date=goal_data.target_date,
        status="active"
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    
    return goal


@app.get("/goals", response_model=List[GoalResponse])
async def list_goals(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all goals, optionally filtered by status
    """
    query = db.query(Goal)
    if status:
        query = query.filter(Goal.status == status)
    
    goals = query.order_by(Goal.created_at.desc()).all()
    return goals


@app.get("/goals/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific goal by ID
    """
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@app.delete("/goals/{goal_id}")
async def delete_goal(
    goal_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a goal
    """
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    db.delete(goal)
    db.commit()
    
    return {"message": "Goal deleted", "goal_id": goal_id}


# ==================== ROADMAP ENDPOINTS ====================

@app.post("/goals/{goal_id}/roadmap", response_model=RoadmapResponse)
async def generate_roadmap(
    goal_id: int,
    context: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Generate AI roadmap for a goal
    """
    # Check if goal exists
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # Check if roadmap already exists
    existing_roadmap = db.query(Roadmap).filter(Roadmap.goal_id == goal_id).first()
    if existing_roadmap and existing_roadmap.approved == 1:
        raise HTTPException(
            status_code=400, 
            detail="Approved roadmap already exists for this goal"
        )
    
    # Generate roadmap using Gemini
    roadmap_text = await gemini_service.generate_roadmap(
        goal=goal.title,
        context=context or goal.description
    )
    
    # Create or update roadmap
    if existing_roadmap:
        existing_roadmap.roadmap_text = roadmap_text
        existing_roadmap.updated_at = datetime.utcnow()
        roadmap = existing_roadmap
    else:
        roadmap = Roadmap(
            goal_id=goal_id,
            roadmap_text=roadmap_text,
            approved=0
        )
        db.add(roadmap)
    
    db.commit()
    db.refresh(roadmap)
    
    return roadmap


@app.get("/goals/{goal_id}/roadmap", response_model=RoadmapResponse)
async def get_roadmap(
    goal_id: int,
    db: Session = Depends(get_db)
):
    """
    Get roadmap for a specific goal
    """
    roadmap = db.query(Roadmap).filter(Roadmap.goal_id == goal_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return roadmap


@app.put("/roadmaps/{roadmap_id}/approve")
async def approve_roadmap(
    roadmap_id: int,
    db: Session = Depends(get_db)
):
    """
    Approve a roadmap and start generating tasks
    """
    roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    
    roadmap.approved = 1
    roadmap.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Roadmap approved", "roadmap_id": roadmap_id}


@app.post("/roadmaps/{roadmap_id}/refine", response_model=RoadmapResponse)
async def refine_roadmap(
    roadmap_id: int,
    feedback: str,
    db: Session = Depends(get_db)
):
    """
    Refine roadmap based on user feedback
    """
    roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    
    # Build conversation history
    conversation_history = [
        {"role": "assistant", "content": roadmap.roadmap_text},
        {"role": "user", "content": feedback}
    ]
    
    # Refine roadmap
    refined_text = await gemini_service.refine_roadmap(
        current_roadmap=roadmap.roadmap_text,
        user_feedback=feedback,
        conversation_history=conversation_history
    )
    
    roadmap.roadmap_text = refined_text
    roadmap.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(roadmap)
    
    return roadmap


# ==================== TASK ENDPOINTS ====================

@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new task
    """
    task = Task(
        milestone_id=task_data.milestone_id,
        title=task_data.title,
        description=task_data.description,
        category=task_data.category,
        priority=task_data.priority,
        scheduled_date=task_data.scheduled_date,
        status=0  # DUE
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # Create audit log
    audit = AuditLog(
        task_id=task.id,
        action="created",
        new_value=task.title,
        reason="Task created"
    )
    db.add(audit)
    db.commit()
    
    return task


@app.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    db: Session = Depends(get_db)
):
    """
    List all tasks
    """
    tasks = db.query(Task).order_by(Task.scheduled_date.desc()).all()
    return tasks


@app.get("/tasks/today", response_model=DailyTasksResponse)
async def get_today_tasks(
    db: Session = Depends(get_db)
):
    """
    Get all tasks scheduled for today
    """
    today = datetime.utcnow().date()
    tasks = db.query(Task).filter(
        Task.scheduled_date >= datetime.combine(today, datetime.min.time()),
        Task.scheduled_date < datetime.combine(today + timedelta(days=1), datetime.min.time())
    ).order_by(Task.priority.desc(), Task.created_at).all()
    
    return {
        "date": today,
        "tasks": tasks,
        "total": len(tasks),
        "completed": sum(1 for t in tasks if t.status == 1),
        "due": sum(1 for t in tasks if t.status == 0),
        "missed": sum(1 for t in tasks if t.status == -1)
    }


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific task
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a task
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Track changes for audit log
    changes = []
    
    if task_update.status is not None and task_update.status != task.status:
        old_status = task.status
        task.status = task_update.status
        changes.append(("status", str(old_status), str(task_update.status)))
        
        if task_update.status == 1:  # COMPLETED
            task.completed_date = datetime.utcnow()
    
    if task_update.title is not None:
        changes.append(("title", task.title, task_update.title))
        task.title = task_update.title
    
    if task_update.description is not None:
        task.description = task_update.description
    
    if task_update.priority is not None:
        task.priority = task_update.priority
    
    task.updated_at = datetime.utcnow()
    
    # Create audit logs for changes
    for field, old_val, new_val in changes:
        audit = AuditLog(
            task_id=task.id,
            action="updated",
            field_name=field,
            old_value=old_val,
            new_value=new_val,
            reason=task_update.reason or "User update"
        )
        db.add(audit)
    
    db.commit()
    db.refresh(task)
    
    return task


@app.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a task
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db.delete(task)
    db.commit()
    
    return {"message": "Task deleted", "task_id": task_id}


# ==================== STATISTICS ENDPOINTS ====================

@app.get("/stats/overview")
async def get_overview_stats(
    db: Session = Depends(get_db)
):
    """
    Get overall statistics
    """
    total_goals = db.query(Goal).count()
    active_goals = db.query(Goal).filter(Goal.status == "active").count()
    total_tasks = db.query(Task).count()
    completed_tasks = db.query(Task).filter(Task.status == 1).count()
    missed_tasks = db.query(Task).filter(Task.status == -1).count()
    
    return {
        "goals": {
            "total": total_goals,
            "active": active_goals
        },
        "tasks": {
            "total": total_tasks,
            "completed": completed_tasks,
            "missed": missed_tasks,
            "completion_rate": round(completed_tasks / total_tasks * 100, 2) if total_tasks > 0 else 0
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )