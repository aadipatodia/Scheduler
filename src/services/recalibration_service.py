"""
Background service for automatic task recalibration
"""
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from ..database import SessionLocal
from ..models import User, Task, Goal, RecalibrationLog
from .gemini_service import GeminiService


class RecalibrationService:
    """
    Service for automatic recalibration of tasks based on missed deadlines
    """
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.gemini_service = GeminiService()
        self.is_running = False
    
    def start(self):
        """Start the background scheduler"""
        if self.is_running:
            logger.warning("Recalibration service is already running")
            return
        
        # Schedule daily recalibration at midnight
        self.scheduler.add_job(
            self.run_daily_recalibration,
            trigger=CronTrigger(hour=0, minute=0),
            id='daily_recalibration',
            name='Daily Task Recalibration',
            replace_existing=True
        )
        
        self.scheduler.start()
        self.is_running = True
        logger.info("Recalibration service started")
    
    def stop(self):
        """Stop the background scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Recalibration service stopped")
    
    def run_daily_recalibration(self):
        """
        Main recalibration logic - runs daily
        """
        logger.info("Starting daily recalibration...")
        
        db = SessionLocal()
        try:
            # Identify missed tasks from yesterday
            yesterday = datetime.utcnow().date() - timedelta(days=1)
            missed_tasks = db.query(Task).filter(
                Task.scheduled_date >= datetime.combine(yesterday, datetime.min.time()),
                Task.scheduled_date < datetime.combine(yesterday + timedelta(days=1), datetime.min.time()),
                Task.status == 0  # DUE (not completed)
            ).all()
            
            if not missed_tasks:
                logger.info("No missed tasks found")
                return
            
            # Mark tasks as missed
            for task in missed_tasks:
                task.status = -1  # MISSED
            
            db.commit()
            logger.info(f"Marked {len(missed_tasks)} tasks as missed")
            
            # Group missed tasks by goal
            tasks_by_goal = {}
            for task in missed_tasks:
                if task.milestone and task.milestone.goal:
                    goal_id = task.milestone.goal_id
                    if goal_id not in tasks_by_goal:
                        tasks_by_goal[goal_id] = []
                    tasks_by_goal[goal_id].append(task)
            
            # Recalibrate for each affected goal
            for goal_id, tasks in tasks_by_goal.items():
                # Note: This is a sync function, but we're calling async method
                # In production, you'd want to use asyncio.run() or make this async
                import asyncio
                try:
                    asyncio.run(self.recalibrate_goal(db, goal_id, tasks))
                except RuntimeError:
                    # If event loop is already running, create a new one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.recalibrate_goal(db, goal_id, tasks))
                    loop.close()
            
            logger.info("Daily recalibration completed")
            
        except Exception as e:
            logger.error(f"Error during recalibration: {str(e)}")
            db.rollback()
        finally:
            db.close()
    
    async def recalibrate_goal(self, db: Session, goal_id: int, missed_tasks: list):
        """
        Recalibrate schedule for a specific goal based on missed tasks
        
        Args:
            db: Database session
            goal_id: Goal ID to recalibrate
            missed_tasks: List of missed tasks
        """
        logger.info(f"Recalibrating goal {goal_id} with {len(missed_tasks)} missed tasks")
        
        try:
            # Get goal information
            goal = db.query(Goal).filter(Goal.id == goal_id).first()
            if not goal:
                logger.warning(f"Goal {goal_id} not found")
                return
            
            # Calculate remaining timeline
            if goal.target_date:
                remaining_days = (goal.target_date - datetime.utcnow()).days
            else:
                remaining_days = 90  # Default assumption
            
            # Prepare missed tasks data for Gemini
            missed_tasks_data = [
                {
                    "title": task.title,
                    "description": task.description,
                    "scheduled_date": task.scheduled_date.isoformat() if task.scheduled_date else None,
                    "priority": task.priority
                }
                for task in missed_tasks
            ]
            
            # Get AI analysis
            analysis = await self.gemini_service.analyze_missed_tasks(
                missed_tasks=missed_tasks_data,
                remaining_timeline=remaining_days,
                goal_description=f"{goal.title}: {goal.description or ''}"
            )
            
            # Log the recalibration
            recalibration_log = RecalibrationLog(
                goal_id=goal_id,
                reason=f"Missed {len(missed_tasks)} tasks",
                changes_made=str(analysis.get('recommendations', [])),
                tasks_affected=str([task.id for task in missed_tasks])
            )
            db.add(recalibration_log)
            
            # Apply timeline adjustment if needed
            if analysis.get('timeline_adjustment_needed') and goal.target_date:
                adjustment_days = analysis.get('suggested_adjustment_days', 0)
                if adjustment_days > 0:
                    goal.target_date = goal.target_date + timedelta(days=adjustment_days)
                    logger.info(f"Adjusted goal {goal_id} timeline by {adjustment_days} days")
            
            # Update priority of remaining tasks if recommended
            priority_task_titles = analysis.get('priority_tasks', [])
            if priority_task_titles:
                # Find and boost priority of recommended tasks
                for title in priority_task_titles[:5]:  # Limit to top 5
                    upcoming_task = db.query(Task).filter(
                        Task.milestone_id.in_([m.id for m in goal.milestones]),
                        Task.title.contains(title[:50]),  # Partial match
                        Task.status == 0  # Only DUE tasks
                    ).first()
                    
                    if upcoming_task and upcoming_task.priority < 5:
                        upcoming_task.priority = min(upcoming_task.priority + 1, 5)
            
            db.commit()
            logger.info(f"Recalibration completed for goal {goal_id}")
            
            # Log the motivation message
            logger.info(f"Motivation: {analysis.get('motivation_message', 'Keep going!')}")
            
        except Exception as e:
            logger.error(f"Error recalibrating goal {goal_id}: {str(e)}")
            db.rollback()
    
    def manual_recalibration(self, goal_id: int):
        """
        Trigger manual recalibration for a specific goal
        
        Args:
            goal_id: Goal ID to recalibrate
        """
        logger.info(f"Manual recalibration triggered for goal {goal_id}")
        
        db = SessionLocal()
        try:
            # Get all missed tasks for this goal
            missed_tasks = db.query(Task).join(Task.milestone).filter(
                Task.milestone.has(goal_id=goal_id),
                Task.status == -1  # MISSED
            ).all()
            
            if missed_tasks:
                import asyncio
                try:
                    asyncio.run(self.recalibrate_goal(db, goal_id, missed_tasks))
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.recalibrate_goal(db, goal_id, missed_tasks))
                    loop.close()
            else:
                logger.info(f"No missed tasks found for goal {goal_id}")
                
        except Exception as e:
            logger.error(f"Error in manual recalibration: {str(e)}")
            db.rollback()
        finally:
            db.close()


# Global instance
recalibration_service = RecalibrationService()


def start_recalibration_service():
    """Start the recalibration background service"""
    recalibration_service.start()


def stop_recalibration_service():
    """Stop the recalibration background service"""
    recalibration_service.stop()