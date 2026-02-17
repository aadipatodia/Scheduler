"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ==================== GOAL SCHEMAS ====================

class GoalCreate(BaseModel):
    """Schema for creating a new goal"""
    title: str = Field(..., min_length=1, max_length=255, description="Goal title")
    description: Optional[str] = Field(None, description="Detailed description of the goal")
    target_date: Optional[datetime] = Field(None, description="Target completion date")


class GoalResponse(BaseModel):
    """Schema for goal responses"""
    id: int
    title: str
    description: Optional[str]
    target_date: Optional[datetime]
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ==================== ROADMAP SCHEMAS ====================

class RoadmapCreate(BaseModel):
    """Schema for creating/updating a roadmap"""
    goal_id: int
    context: Optional[str] = Field(None, description="Additional context for roadmap generation")


class RoadmapResponse(BaseModel):
    """Schema for roadmap responses"""
    id: int
    goal_id: int
    roadmap_text: str
    phases: Optional[str] = None
    approved: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class RoadmapRefine(BaseModel):
    """Schema for refining a roadmap"""
    feedback: str = Field(..., description="User feedback for refinement")


# ==================== MILESTONE SCHEMAS ====================

class MilestoneCreate(BaseModel):
    """Schema for creating a milestone"""
    goal_id: int
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    order_index: int = 0
    target_date: Optional[datetime] = None


class MilestoneResponse(BaseModel):
    """Schema for milestone responses"""
    id: int
    goal_id: int
    title: str
    description: Optional[str]
    order_index: int
    target_date: Optional[datetime]
    completed_date: Optional[datetime]
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ==================== TASK SCHEMAS ====================

class TaskCreate(BaseModel):
    """Schema for creating a task"""
    milestone_id: Optional[int] = None
    title: str = Field(..., min_length=1, description="Task title")
    description: Optional[str] = Field(None, description="Detailed task description")
    category: str = Field(default="daily", description="Task category: daily, weekly, milestone")
    priority: int = Field(default=0, ge=0, le=5, description="Priority level 0-5")
    scheduled_date: Optional[datetime] = Field(None, description="When task should be completed")


class TaskUpdate(BaseModel):
    """Schema for updating a task"""
    title: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    status: Optional[int] = Field(None, ge=-1, le=1, description="Status: -1=missed, 0=due, 1=completed")
    priority: Optional[int] = Field(None, ge=0, le=5)
    reason: Optional[str] = Field(None, description="Reason for the update (for audit log)")


class TaskResponse(BaseModel):
    """Schema for task responses"""
    id: int
    milestone_id: Optional[int]
    title: str
    description: Optional[str]
    category: str
    status: int
    priority: int
    scheduled_date: Optional[datetime]
    completed_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DailyTasksResponse(BaseModel):
    """Schema for daily tasks overview"""
    date: datetime
    tasks: List[TaskResponse]
    total: int
    completed: int
    due: int
    missed: int


# ==================== AUDIT LOG SCHEMAS ====================

class AuditLogResponse(BaseModel):
    """Schema for audit log entries"""
    id: int
    task_id: Optional[int]
    action: str
    field_name: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    reason: Optional[str]
    timestamp: datetime
    
    class Config:
        from_attributes = True


# ==================== CONVERSATION SCHEMAS ====================

class ConversationMessage(BaseModel):
    """Schema for conversation messages"""
    role: str = Field(..., description="Role: user or assistant")
    content: str = Field(..., description="Message content")


class ConversationResponse(BaseModel):
    """Schema for conversation history"""
    id: int
    goal_id: Optional[int]
    role: str
    content: str
    timestamp: datetime
    
    class Config:
        from_attributes = True


# ==================== RECALIBRATION SCHEMAS ====================

class RecalibrationRequest(BaseModel):
    """Schema for triggering recalibration"""
    goal_id: int
    force: bool = Field(default=False, description="Force recalibration even if not needed")


class RecalibrationResponse(BaseModel):
    """Schema for recalibration results"""
    severity: str
    recommendations: List[str]
    timeline_adjustment_needed: bool
    suggested_adjustment_days: int
    priority_tasks: List[str]
    motivation_message: str