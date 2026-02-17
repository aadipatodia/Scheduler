"""
Service for interacting with Google Gemini API
"""
import os
import re
import json
import math
from datetime import date
from typing import List, Dict, Optional, Tuple
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
        target_date: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Generate a roadmap for achieving a long-term goal.
        Returns a dict with 'phases' (list of structured phase dicts) and 'roadmap_text' (raw text fallback).
        """
        deadline_instruction = ""
        if target_date:
            deadline_instruction = f"""
CRITICAL DEADLINE CONSTRAINT:
The user has set a hard deadline of {target_date} to achieve this goal.
You MUST ensure that ALL phases fit within this deadline.
Distribute phases proportionally across the available time.
If the deadline is tight, prioritize the most impactful tasks and be honest about what's realistic.
"""

        today = date.today().strftime("%B %d, %Y")

        system_prompt = f"""You are an expert planning assistant. Break down the user's goal into a structured roadmap.

TODAY'S DATE IS: {today}. All timelines must start from today. Never use dates in the past.

{deadline_instruction}
You MUST respond with ONLY a valid JSON object. No markdown, no extra text, no code fences.

The JSON must follow this EXACT structure:
{{
  "phases": [
    {{
      "title": "Phase title here",
      "timeline": "e.g. 2 Weeks, Month 1-2, etc.",
      "goal": "One sentence describing what this phase achieves.",
      "tasks": [
        "Full description of task 1",
        "Full description of task 2",
        "Full description of task 3"
      ],
      "success_criteria": [
        "How to know this phase is complete - criterion 1",
        "Criterion 2"
      ]
    }}
  ]
}}

RULES:
- Minimum 3 phases, maximum 10 phases.
- Each task and criterion must be a COMPLETE sentence. Never cut off mid-sentence.
- Each phase must have at least 2 tasks and at least 1 success criterion.
- Be realistic, specific, and encouraging.
- The response must be ONLY the JSON object, nothing else."""

        prompt = f"{system_prompt}\n\nGoal: {goal}"
        if context:
            prompt += f"\nAdditional Context: {context}"
        if target_date:
            prompt += f"\nDeadline: {target_date}"

        response = self.model.generate_content(prompt)
        raw_text = response.text

        phases_data = self._extract_json(raw_text)
        if phases_data and "phases" in phases_data:
            return {"phases": phases_data["phases"][:10], "roadmap_text": raw_text}

        return {"phases": None, "roadmap_text": raw_text}
    
    async def refine_roadmap(
        self,
        current_phases_json: str,
        user_feedback: str
    ) -> Dict:
        """
        Refine an existing roadmap based on user feedback. Returns structured JSON.
        """
        today = date.today().strftime("%B %d, %Y")

        system_prompt = f"""You are helping refine a roadmap based on user feedback.

TODAY'S DATE IS: {today}. All timelines must start from today. Never use dates in the past.

Adjust based on the user's requests (timelines, add/remove phases, change priorities, etc.).
Keep it realistic and achievable.

You MUST respond with ONLY a valid JSON object. No markdown, no extra text, no code fences.

The JSON must follow this EXACT structure:
{{
  "phases": [
    {{
      "title": "Phase title here",
      "timeline": "e.g. 2 Weeks, Month 1-2, etc.",
      "goal": "One sentence describing what this phase achieves.",
      "tasks": [
        "Full description of task 1",
        "Full description of task 2"
      ],
      "success_criteria": [
        "Criterion 1",
        "Criterion 2"
      ]
    }}
  ]
}}

RULES:
- Minimum 3 phases, maximum 10 phases.
- Each task and criterion must be a COMPLETE sentence.
- The response must be ONLY the JSON object, nothing else."""

        prompt = f"""{system_prompt}

Current roadmap:
{current_phases_json}

User's requested changes: {user_feedback}"""

        response = self.model.generate_content(prompt)
        raw_text = response.text

        phases_data = self._extract_json(raw_text)
        if phases_data and "phases" in phases_data:
            return {"phases": phases_data["phases"][:10], "roadmap_text": raw_text}

        return {"phases": None, "roadmap_text": raw_text}
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from Gemini response, handling code fences."""
        cleaned = text.strip()
        # Remove markdown code fences if present
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = cleaned.find('{')
            end = cleaned.rfind('}')
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start:end + 1])
                except json.JSONDecodeError:
                    pass
        return None

    @staticmethod
    def _parse_timeline_to_days(timeline: str) -> Optional[int]:
        """
        Parse a human-readable timeline string into an approximate day count.
        Examples: '2 Weeks' -> 14, 'Month 1-2' -> 60, '3 Months' -> 90, 'Week 1' -> 7
        """
        if not timeline:
            return None

        text = timeline.lower().strip()

        # "X weeks" or "X week"
        m = re.search(r'(\d+)\s*weeks?', text)
        if m:
            return int(m.group(1)) * 7

        # "week X-Y" → (Y - X + 1) weeks
        m = re.search(r'weeks?\s*(\d+)\s*[-–to]+\s*(\d+)', text)
        if m:
            return (int(m.group(2)) - int(m.group(1)) + 1) * 7

        # "week X" → 1 week
        m = re.search(r'weeks?\s*(\d+)$', text)
        if m:
            return 7

        # "X months" or "X month"
        m = re.search(r'(\d+)\s*months?', text)
        if m:
            return int(m.group(1)) * 30

        # "month X-Y" → (Y - X + 1) months
        m = re.search(r'months?\s*(\d+)\s*[-–to]+\s*(\d+)', text)
        if m:
            return (int(m.group(2)) - int(m.group(1)) + 1) * 30

        # "month X" → 1 month
        m = re.search(r'months?\s*(\d+)$', text)
        if m:
            return 30

        # "X days"
        m = re.search(r'(\d+)\s*days?', text)
        if m:
            return int(m.group(1))

        return None

    @staticmethod
    def compute_phase_day_ranges(phases: list, total_days: int) -> List[Tuple[int, int, int]]:
        """
        Compute (start_day, end_day, duration) for each phase respecting their
        timeline strings. Days are 1-based (day 1 = today).

        Algorithm:
        1. Parse each phase's timeline to get a duration hint.
        2. If all hints fit within total_days, use them directly.
        3. If they overflow, scale them proportionally to fit.
        4. Phases without a parseable timeline share remaining days equally.
        """
        n = len(phases)
        if n == 0:
            return []

        parsed = [GeminiService._parse_timeline_to_days(p.get('timeline', '')) for p in phases]

        known_total = sum(d for d in parsed if d is not None)
        unknown_count = sum(1 for d in parsed if d is None)

        if unknown_count == n:
            # No parseable timelines — split evenly
            base = total_days // n
            remainder = total_days % n
            durations = [base + (1 if i < remainder else 0) for i in range(n)]
        elif unknown_count > 0:
            # Mix: give known phases their share, split the rest
            leftover = max(total_days - known_total, unknown_count)
            per_unknown = leftover // unknown_count
            extra = leftover % unknown_count
            durations = []
            for i, d in enumerate(parsed):
                if d is not None:
                    durations.append(d)
                else:
                    durations.append(per_unknown + (1 if i < extra else 0))
        else:
            durations = [d for d in parsed]  # All known

        # Scale to fit total_days if they exceed or fall short
        dur_sum = sum(durations)
        if dur_sum != total_days and dur_sum > 0:
            scale = total_days / dur_sum
            durations = [max(int(round(d * scale)), 1) for d in durations]
            # Fix rounding errors
            diff = total_days - sum(durations)
            for i in range(abs(diff)):
                idx = i % n
                durations[idx] += 1 if diff > 0 else -1
                durations[idx] = max(durations[idx], 1)

        # Convert to (start_day, end_day, duration)
        ranges = []
        current = 1
        for dur in durations:
            dur = max(dur, 1)
            ranges.append((current, current + dur - 1, dur))
            current += dur

        return ranges

    async def generate_daily_tasks_from_roadmap(
        self,
        phases: list,
        goal_title: str,
        total_days: int
    ) -> list:
        """
        Generate granular daily tasks from roadmap phases.
        Phase day-ranges are computed from the phase timeline strings so
        daily tasks respect the roadmap schedule.
        """
        today = date.today().strftime("%B %d, %Y")
        phase_ranges = self.compute_phase_day_ranges(phases, total_days)

        # Build a strict schedule description for the prompt
        schedule_text = ""
        phases_text = ""
        for i, phase in enumerate(phases):
            start_d, end_d, dur = phase_ranges[i] if i < len(phase_ranges) else (1, total_days, total_days)
            schedule_text += f"  Phase {i + 1}: Day {start_d} – Day {end_d} ({dur} days)\n"
            phases_text += f"\nPhase {i + 1}: {phase.get('title', '')}  [Day {start_d} – Day {end_d}]\n"
            phases_text += f"  Goal: {phase.get('goal', '')}\n"
            phases_text += f"  Roadmap timeline: {phase.get('timeline', 'N/A')}\n"
            phases_text += f"  Tasks:\n"
            for t in phase.get('tasks', []):
                phases_text += f"    - {t}\n"

        system_prompt = f"""You are an expert productivity coach. Given a roadmap with phases, break each phase's high-level tasks into specific, actionable DAILY tasks.

TODAY'S DATE IS: {today}. Day 1 = today.

CRITICAL SCHEDULE — you MUST follow these day ranges EXACTLY:
{schedule_text}
Tasks for a phase MUST only be scheduled within that phase's day range.
Do NOT put Phase 1 tasks on days that belong to Phase 2, etc.

You MUST respond with ONLY a valid JSON object. No markdown, no extra text, no code fences.

The JSON must follow this EXACT structure:
{{
  "daily_tasks": [
    {{
      "day": 1,
      "phase_index": 0,
      "title": "Short actionable task title",
      "description": "Brief description of what to do",
      "priority": 4
    }}
  ]
}}

RULES:
- day is 1-based (1 = today, 2 = tomorrow, etc.)
- phase_index is 0-based matching the input phases array
- priority is 1-5 (5 = highest)
- Generate 2-4 tasks per day, not more
- EVERY day within a phase's range should have tasks — fill the schedule
- Day 1 MUST have tasks (these show up immediately for the user)
- Tasks should be specific and actionable, not vague
- Each task title must be concise (under 80 chars)
- Tasks should progressively build on each other within a phase
- The response must be ONLY the JSON object, nothing else."""

        prompt = f"""{system_prompt}

Goal: {goal_title}
Total days: {total_days}
Number of phases: {len(phases)}

Roadmap Phases:
{phases_text}

Generate daily tasks in JSON format."""

        response = self.model.generate_content(prompt)
        raw_text = response.text

        data = self._extract_json(raw_text)
        if data and "daily_tasks" in data:
            tasks = data["daily_tasks"]
            # Validate: clamp tasks to their phase's day-range
            for t in tasks:
                pi = t.get("phase_index", 0)
                if 0 <= pi < len(phase_ranges):
                    s, e, _ = phase_ranges[pi]
                    t["day"] = max(s, min(t.get("day", s), e))
            return tasks

        return self._fallback_distribute_tasks(phases, total_days, phase_ranges)

    def _fallback_distribute_tasks(
        self, phases: list, total_days: int,
        phase_ranges: Optional[List[Tuple[int, int, int]]] = None
    ) -> list:
        """
        Distribute phase tasks across their day-ranges as fallback.
        If a phase has fewer tasks than days, each task is split into
        sub-steps (Research, Practice, Review) to fill the schedule with
        2-3 tasks per day.
        """
        daily_tasks = []
        if not phases:
            return daily_tasks

        if phase_ranges is None:
            phase_ranges = self.compute_phase_day_ranges(phases, total_days)

        for phase_idx, phase in enumerate(phases):
            phase_tasks = phase.get('tasks', [])
            if not phase_tasks:
                continue

            start_d, end_d, dur = phase_ranges[phase_idx] if phase_idx < len(phase_ranges) else (1, total_days, total_days)

            # Expand tasks so there are ~2-3 per day within this phase
            target_count = max(dur * 2, len(phase_tasks))
            expanded = []
            if len(phase_tasks) < target_count:
                actions = [
                    ("Study: ", 5),
                    ("Practice: ", 4),
                    ("Review: ", 3),
                ]
                for task_text in phase_tasks:
                    for label, prio in actions:
                        expanded.append((f"{label}{task_text}", task_text, prio))
                        if len(expanded) >= target_count:
                            break
                    if len(expanded) >= target_count:
                        break
                # Fill remaining from other tasks
                idx = 0
                while len(expanded) < target_count and phase_tasks:
                    task_text = phase_tasks[idx % len(phase_tasks)]
                    expanded.append((f"Continue: {task_text}", task_text, 3))
                    idx += 1
                    if idx > target_count * 2:
                        break
            else:
                for j, task_text in enumerate(phase_tasks):
                    expanded.append((task_text, task_text, max(5 - j, 1)))

            # Distribute expanded tasks evenly across the phase's days
            for j, (title, desc, prio) in enumerate(expanded):
                task_day = start_d + (j * dur) // len(expanded)
                task_day = max(start_d, min(task_day, end_d))
                daily_tasks.append({
                    "day": task_day,
                    "phase_index": phase_idx,
                    "title": title,
                    "description": desc,
                    "priority": prio
                })

        return daily_tasks

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