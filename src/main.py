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
from .models import User, Goal, Roadmap, Milestone, Task, AuditLog, TaskStatus
from .auth import create_session_value, COOKIE_NAME, get_current_user
from .services.gemini_service import GeminiService
from .schemas import (
    PhoneLogin, UserResponse,
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

@app.get("/roadmap", response_class=HTMLResponse)
async def roadmap_page(request: Request):
    """Serve the roadmap journey page"""
    return templates.TemplateResponse("roadmap.html", {"request": request})
# ==================== API ROUTES ====================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}


# ==================== AUTH ENDPOINTS ====================

@app.post("/auth/login", response_model=UserResponse)
async def login(credentials: PhoneLogin, db: Session = Depends(get_db)):
    """Log in (or auto-create) a user by phone number."""
    phone = credentials.phone.strip()
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        user = User(phone=phone)
        db.add(user)
        db.commit()
        db.refresh(user)

    response = JSONResponse(
        content=UserResponse.model_validate(user).model_dump(mode="json"),
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_value(user.id),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return response


@app.post("/auth/logout")
async def logout():
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ==================== GOAL ENDPOINTS ====================

@app.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    goal_data: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new long-term goal
    """
    goal = Goal(
        user_id=current_user.id,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all goals for the current user, optionally filtered by status
    """
    query = db.query(Goal).filter(Goal.user_id == current_user.id)
    if status:
        query = query.filter(Goal.status == status)
    
    goals = query.order_by(Goal.created_at.desc()).all()
    return goals


def _get_user_goal(goal_id: int, user_id: int, db: Session) -> Goal:
    """Helper: fetch a goal that belongs to the given user or raise 404."""
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@app.get("/goals/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific goal by ID (must belong to current user)
    """
    return _get_user_goal(goal_id, current_user.id, db)


@app.delete("/goals/{goal_id}")
async def delete_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a goal and all related data (roadmap, milestones, tasks, audit logs)
    """
    from .models import RecalibrationLog, ConversationHistory

    goal = _get_user_goal(goal_id, current_user.id, db)

    try:
        milestone_ids = [m.id for m in db.query(Milestone.id).filter(Milestone.goal_id == goal.id).all()]
        if milestone_ids:
            task_ids = [t.id for t in db.query(Task.id).filter(Task.milestone_id.in_(milestone_ids)).all()]
            if task_ids:
                db.query(AuditLog).filter(AuditLog.task_id.in_(task_ids)).delete(synchronize_session=False)
            db.query(Task).filter(Task.milestone_id.in_(milestone_ids)).delete(synchronize_session=False)
        db.query(Milestone).filter(Milestone.goal_id == goal.id).delete(synchronize_session=False)
        db.query(Roadmap).filter(Roadmap.goal_id == goal.id).delete(synchronize_session=False)
        db.query(RecalibrationLog).filter(RecalibrationLog.goal_id == goal.id).delete(synchronize_session=False)
        db.query(ConversationHistory).filter(ConversationHistory.goal_id == goal.id).delete(synchronize_session=False)
        db.query(Goal).filter(Goal.id == goal.id).delete(synchronize_session=False)

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete goal: {str(e)}")

    return {"message": "Goal deleted", "goal_id": goal_id}


# ==================== ROADMAP ENDPOINTS ====================

@app.post("/goals/{goal_id}/roadmap", response_model=RoadmapResponse)
async def generate_roadmap(
    goal_id: int,
    context: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate AI roadmap for a goal (returns structured JSON phases)
    """
    import json as json_module
    
    goal = _get_user_goal(goal_id, current_user.id, db)
    
    existing_roadmap = db.query(Roadmap).filter(Roadmap.goal_id == goal_id).first()
    if existing_roadmap and existing_roadmap.approved == 1:
        raise HTTPException(
            status_code=400, 
            detail="Approved roadmap already exists for this goal"
        )
    
    target_date_str = None
    if goal.target_date:
        target_date_str = goal.target_date.strftime("%B %d, %Y")
    
    result = await gemini_service.generate_roadmap(
        goal=goal.title,
        context=context or goal.description,
        target_date=target_date_str
    )
    
    roadmap_text = result.get("roadmap_text", "")
    phases_json = json_module.dumps(result["phases"]) if result.get("phases") else None
    
    if existing_roadmap:
        existing_roadmap.roadmap_text = roadmap_text
        existing_roadmap.phases = phases_json
        existing_roadmap.updated_at = datetime.utcnow()
        roadmap = existing_roadmap
    else:
        roadmap = Roadmap(
            goal_id=goal_id,
            roadmap_text=roadmap_text,
            phases=phases_json,
            approved=0
        )
        db.add(roadmap)
    
    db.commit()
    db.refresh(roadmap)
    
    return roadmap


@app.get("/goals/{goal_id}/roadmap", response_model=RoadmapResponse)
async def get_roadmap(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get roadmap for a specific goal (must belong to current user)
    """
    _get_user_goal(goal_id, current_user.id, db)
    roadmap = db.query(Roadmap).filter(Roadmap.goal_id == goal_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return roadmap


@app.put("/roadmaps/{roadmap_id}/approve")
async def approve_roadmap(
    roadmap_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Approve a roadmap and generate daily tasks from phases
    """
    import json as json_module

    roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")

    goal = _get_user_goal(roadmap.goal_id, current_user.id, db)

    # Mark roadmap as approved
    roadmap.approved = 1
    roadmap.updated_at = datetime.utcnow()

    # Parse phases from roadmap
    phases = []
    if roadmap.phases:
        try:
            parsed = json_module.loads(roadmap.phases) if isinstance(roadmap.phases, str) else roadmap.phases
            if isinstance(parsed, list):
                phases = parsed
        except (json_module.JSONDecodeError, TypeError):
            pass

    if not phases:
        db.commit()
        return {"message": "Roadmap approved (no phases to generate tasks from)", "roadmap_id": roadmap_id, "tasks_created": 0}

    # Calculate total days for the roadmap
    today = datetime.utcnow().date()
    if goal.target_date:
        total_days = max((goal.target_date.date() - today).days, len(phases))
    else:
        total_days = len(phases) * 7  # Default: ~1 week per phase

    # Clean up old milestones and tasks for this goal before regenerating
    old_milestones = db.query(Milestone).filter(Milestone.goal_id == goal.id).all()
    for ms in old_milestones:
        db.query(AuditLog).filter(AuditLog.task_id.in_(
            db.query(Task.id).filter(Task.milestone_id == ms.id)
        )).delete(synchronize_session=False)
        db.query(Task).filter(Task.milestone_id == ms.id).delete(synchronize_session=False)
    db.query(Milestone).filter(Milestone.goal_id == goal.id).delete(synchronize_session=False)
    db.flush()

    # Compute day ranges per phase from their timeline strings
    phase_ranges = gemini_service.compute_phase_day_ranges(phases, total_days)

    # Create Milestone records from phases using computed ranges
    milestone_map = {}  # phase_index -> milestone

    for i, phase in enumerate(phases):
        start_d, end_d, dur = phase_ranges[i] if i < len(phase_ranges) else (1, total_days, total_days)
        phase_start = today + timedelta(days=start_d - 1)
        phase_end = today + timedelta(days=end_d - 1)

        milestone = Milestone(
            goal_id=goal.id,
            title=phase.get('title', f'Phase {i + 1}'),
            description=phase.get('goal', ''),
            order_index=i,
            target_date=datetime.combine(phase_end, datetime.min.time()),
            status="in_progress" if i == 0 else "pending"
        )
        db.add(milestone)
        db.flush()
        milestone_map[i] = milestone

    # Generate daily tasks via Gemini (uses the same phase_ranges internally)
    try:
        daily_tasks = await gemini_service.generate_daily_tasks_from_roadmap(
            phases=phases,
            goal_title=goal.title,
            total_days=total_days
        )
    except Exception as e:
        print(f"Gemini daily task generation failed, using fallback: {e}")
        daily_tasks = gemini_service._fallback_distribute_tasks(phases, total_days, phase_ranges)

    # Create Task records
    tasks_created = 0
    for task_data in daily_tasks:
        day_num = task_data.get("day", 1)
        phase_idx = task_data.get("phase_index", 0)
        scheduled = datetime.combine(today + timedelta(days=day_num - 1), datetime.min.time())

        milestone = milestone_map.get(phase_idx, list(milestone_map.values())[0])

        task = Task(
            user_id=current_user.id,
            milestone_id=milestone.id,
            title=task_data.get("title", "Task"),
            description=task_data.get("description", ""),
            category="daily",
            priority=min(max(task_data.get("priority", 3), 1), 5),
            scheduled_date=scheduled,
            status=0  # DUE
        )
        db.add(task)
        tasks_created += 1

    db.commit()

    return {
        "message": "Roadmap approved! Daily tasks generated.",
        "roadmap_id": roadmap_id,
        "tasks_created": tasks_created,
        "milestones_created": len(milestone_map)
    }


@app.post("/roadmaps/{roadmap_id}/refine", response_model=RoadmapResponse)
async def refine_roadmap(
    roadmap_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Refine roadmap based on user feedback (returns structured JSON phases)
    """
    import json as json_module

    feedback = body.get("feedback", "")
    if not feedback:
        raise HTTPException(status_code=400, detail="Feedback is required")

    roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")

    _get_user_goal(roadmap.goal_id, current_user.id, db)
    
    # Send current phases JSON to Gemini for refinement
    current_data = roadmap.phases if roadmap.phases else roadmap.roadmap_text
    
    result = await gemini_service.refine_roadmap(
        current_phases_json=current_data,
        user_feedback=feedback
    )
    
    roadmap.roadmap_text = result.get("roadmap_text", "")
    if result.get("phases"):
        roadmap.phases = json_module.dumps(result["phases"])
    roadmap.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(roadmap)
    
    return roadmap


# ==================== TASK ENDPOINTS ====================

@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new task
    """
    task = Task(
        user_id=current_user.id,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all tasks for the current user
    """
    tasks = (
        db.query(Task)
        .filter(Task.user_id == current_user.id)
        .order_by(Task.scheduled_date.desc())
        .all()
    )
    return tasks


@app.get("/tasks/today")
async def get_today_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all tasks scheduled for today, enriched with milestone/goal info.
    Automatically reschedules overdue incomplete tasks to today.
    """
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today + timedelta(days=1), datetime.min.time())

    overdue_tasks = db.query(Task).filter(
        Task.user_id == current_user.id,
        Task.scheduled_date < today_start,
        Task.status == 0,
    ).all()

    rescheduled_ids = set()
    for t in overdue_tasks:
        old_date = t.scheduled_date
        t.scheduled_date = today_start
        t.updated_at = datetime.utcnow()
        rescheduled_ids.add(t.id)

        audit = AuditLog(
            task_id=t.id,
            action="rescheduled",
            field_name="scheduled_date",
            old_value=old_date.isoformat() if old_date else None,
            new_value=today_start.isoformat(),
            reason="Auto-rescheduled: incomplete task from a previous day"
        )
        db.add(audit)

    if rescheduled_ids:
        db.commit()

    tasks = db.query(Task).filter(
        Task.user_id == current_user.id,
        Task.scheduled_date >= today_start,
        Task.scheduled_date < today_end,
    ).order_by(Task.priority.desc(), Task.created_at).all()

    enriched_tasks = []
    for t in tasks:
        task_dict = {
            "id": t.id,
            "milestone_id": t.milestone_id,
            "title": t.title,
            "description": t.description,
            "category": t.category,
            "status": t.status,
            "priority": t.priority,
            "scheduled_date": t.scheduled_date.isoformat() if t.scheduled_date else None,
            "completed_date": t.completed_date.isoformat() if t.completed_date else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            "milestone_title": None,
            "goal_title": None,
            "rescheduled": t.id in rescheduled_ids,
        }
        if t.milestone_id and t.milestone:
            task_dict["milestone_title"] = t.milestone.title
            if t.milestone.goal:
                task_dict["goal_title"] = t.milestone.goal.title
        enriched_tasks.append(task_dict)

    return {
        "date": today.isoformat(),
        "tasks": enriched_tasks,
        "total": len(tasks),
        "completed": sum(1 for t in tasks if t.status == 1),
        "due": sum(1 for t in tasks if t.status == 0),
        "missed": sum(1 for t in tasks if t.status == -1),
        "rescheduled": len(rescheduled_ids)
    }


def _get_user_task(task_id: int, user_id: int, db: Session) -> Task:
    """Helper: fetch a task that belongs to the given user or raise 404."""
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific task (must belong to current user)
    """
    return _get_user_task(task_id, current_user.id, db)


@app.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a task (must belong to current user)
    """
    task = _get_user_task(task_id, current_user.id, db)
    
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a task (must belong to current user)
    """
    task = _get_user_task(task_id, current_user.id, db)
    
    db.delete(task)
    db.commit()
    
    return {"message": "Task deleted", "task_id": task_id}


# ==================== STATISTICS ENDPOINTS ====================

@app.get("/stats/overview")
async def get_overview_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get overall statistics for the current user
    """
    total_goals = db.query(Goal).filter(Goal.user_id == current_user.id).count()
    active_goals = db.query(Goal).filter(Goal.user_id == current_user.id, Goal.status == "active").count()
    total_tasks = db.query(Task).filter(Task.user_id == current_user.id).count()
    completed_tasks = db.query(Task).filter(Task.user_id == current_user.id, Task.status == 1).count()
    missed_tasks = db.query(Task).filter(Task.user_id == current_user.id, Task.status == -1).count()
    
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