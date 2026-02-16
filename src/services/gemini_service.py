"""
Service for interacting with Google Gemini API
"""
import os
import json
from typing import List, Dict, Optional
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()


class GeminiService:
    """
    Service class for Google Gemini AI interactions
    """
    
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    async def generate_roadmap(
        self, 
        goal: str, 
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """
        Generate a roadmap for achieving a long-term goal
        
        Args:
            goal: The long-term goal description
            context: Additional context about the user
            conversation_history: Previous conversation for context
            
        Returns:
            AI-generated roadmap text
        """
        system_prompt = """You are an expert planning assistant helping users break down long-term goals into actionable roadmaps.

Your task is to:
1. Analyze the user's goal
2. Break it down into logical phases/milestones
3. Suggest a realistic timeline
4. Identify key tasks and learning objectives
5. Consider dependencies and prerequisites

Format your response as a structured roadmap with:
- Clear phases/milestones
- Timeline estimates
- Key tasks for each phase
- Success criteria

Be realistic but encouraging. Account for learning curves and potential setbacks."""

        # Build the prompt
        prompt = f"{system_prompt}\n\n"
        
        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                prompt += f"{role.capitalize()}: {content}\n\n"
        
        # Add current request
        prompt += f"User: Goal: {goal}"
        if context:
            prompt += f"\n\nAdditional Context: {context}"
        
        prompt += "\n\nAssistant: "
        
        # Generate response
        response = self.model.generate_content(prompt)
        return response.text
    
    async def refine_roadmap(
        self,
        current_roadmap: str,
        user_feedback: str,
        conversation_history: List[Dict]
    ) -> str:
        """
        Refine an existing roadmap based on user feedback
        
        Args:
            current_roadmap: The current roadmap text
            user_feedback: User's requested changes
            conversation_history: Full conversation history
            
        Returns:
            Updated roadmap text
        """
        system_prompt = """You are helping refine a roadmap based on user feedback.

Keep the overall structure but adjust based on the user's requests. They might want to:
- Adjust timelines
- Add or remove phases
- Change priorities
- Add specific skills or tasks
- Make it more/less ambitious

Maintain consistency and ensure the revised roadmap is still realistic and achievable."""

        # Build the prompt with conversation history
        prompt = f"{system_prompt}\n\n"
        
        for msg in conversation_history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            prompt += f"{role.capitalize()}: {content}\n\n"
        
        prompt += f"User: Current roadmap:\n{current_roadmap}\n\nRequested changes: {user_feedback}\n\nPlease provide an updated roadmap.\n\nAssistant: "
        
        # Generate response
        response = self.model.generate_content(prompt)
        return response.text
    
    async def generate_weekly_tasks(
        self,
        milestone: str,
        milestone_description: str,
        week_number: int,
        total_weeks: int
    ) -> List[Dict[str, str]]:
        """
        Generate specific weekly tasks for a milestone
        
        Args:
            milestone: Milestone title
            milestone_description: Detailed description
            week_number: Current week number
            total_weeks: Total weeks allocated for this milestone
            
        Returns:
            List of task dictionaries
        """
        system_prompt = """You are breaking down a milestone into weekly actionable tasks.

Generate 3-7 specific, actionable tasks for the given week that:
1. Are concrete and measurable
2. Can realistically be completed in a week
3. Build upon previous weeks (if not week 1)
4. Progress towards the milestone goal
5. Include mix of learning, practice, and building

Return ONLY a JSON array of tasks with this structure:
[
    {
        "title": "Short task title",
        "description": "Detailed description with acceptance criteria",
        "priority": 1-5 (5 being highest)
    }
]"""

        prompt = f"""{system_prompt}

Milestone: {milestone}
Description: {milestone_description}
Week: {week_number} of {total_weeks}

Generate weekly tasks in JSON format."""
        
        # Generate response
        response = self.model.generate_content(prompt)
        response_text = response.text
        
        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()
        
        try:
            tasks = json.loads(json_str)
            return tasks
        except json.JSONDecodeError:
            # Fallback: create a single task if JSON parsing fails
            return [{
                "title": "Complete milestone phase",
                "description": milestone_description,
                "priority": 3
            }]
    
    async def analyze_missed_tasks(
        self,
        missed_tasks: List[Dict],
        remaining_timeline: int,
        goal_description: str
    ) -> Dict[str, any]:
        """
        Analyze missed tasks and suggest recalibration
        
        Args:
            missed_tasks: List of missed task information
            remaining_timeline: Days remaining to goal
            goal_description: Overall goal
            
        Returns:
            Dictionary with recalibration suggestions
        """
        system_prompt = """You are analyzing missed tasks to help recalibrate a schedule.

Assess:
1. How many tasks were missed
2. Why they might have been missed (too ambitious, prerequisites missing, etc.)
3. Impact on the overall timeline
4. Whether the goal deadline needs adjustment
5. What tasks should be prioritized now

Provide realistic recommendations that keep the user motivated while being honest about challenges.

Return a JSON object with:
{
    "severity": "low|medium|high",
    "recommendations": ["list of specific recommendations"],
    "timeline_adjustment_needed": true/false,
    "suggested_adjustment_days": 0,
    "priority_tasks": ["tasks to focus on next"],
    "motivation_message": "encouraging message"
}"""

        task_summary = f"Missed {len(missed_tasks)} tasks:\n"
        for task in missed_tasks[:10]:  # Limit to 10 for context
            task_summary += f"- {task.get('title', 'Unnamed task')}\n"
        
        prompt = f"""{system_prompt}

Goal: {goal_description}
Days remaining: {remaining_timeline}

{task_summary}

Analyze and provide recalibration recommendations in JSON format."""
        
        # Generate response
        response = self.model.generate_content(prompt)
        response_text = response.text
        
        # Extract JSON
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()
        
        try:
            analysis = json.loads(json_str)
            return analysis
        except json.JSONDecodeError:
            # Fallback response
            return {
                "severity": "medium",
                "recommendations": ["Review and prioritize remaining tasks", "Focus on core objectives"],
                "timeline_adjustment_needed": False,
                "suggested_adjustment_days": 0,
                "priority_tasks": [],
                "motivation_message": "Keep going! Small adjustments can get you back on track."
            }