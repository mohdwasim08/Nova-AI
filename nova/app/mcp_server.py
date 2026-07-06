# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Nova MCP Server — exposes Nova's productivity tools over the MCP protocol.

This server can be run standalone (stdio mode) and consumed by any MCP-compatible
client — including the Nova ADK agent itself via McpToolset.

Run with:
    uv run python -m app.mcp_server

Or for development inspection:
    uv run python -m app.mcp_server --help
"""

import os
import sys

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load .env so DB path and credentials are available when server is spawned
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_env_path)

# Import tools after env is loaded (tools.py reads DB on import via store)
from app import tools  # noqa: E402

# ---------------------------------------------------------------------------
# MCP Server Definition
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="nova-productivity",
    instructions=(
        "Nova Productivity MCP Server. Provides tools for managing tasks, goals, "
        "habits, reminders, memory, schedules, and productivity coaching for the "
        "Nova personal productivity assistant."
    ),
)


# ---------------------------------------------------------------------------
# Task Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def nova_list_tasks(
    status: str | None = None,
    category: str | None = None,
) -> dict:
    """List all tasks, optionally filtered by status and/or category.

    Args:
        status: Filter tasks by status. One of: pending, completed, missed.
                Leave empty to return tasks of all statuses.
        category: Filter tasks by category (e.g. DSA, Machine Learning,
                  Communication, Fitness, Personal). Leave empty for all.

    Returns:
        Dictionary with 'status' and 'tasks' list.
    """
    return tools.list_tasks(status=status, category=category)


@mcp.tool()
def nova_create_task(
    title: str,
    description: str | None = None,
    category: str = "Personal",
    priority: str = "medium",
    due_date: str | None = None,
    scheduled_time: str | None = None,
    duration: int | None = None,
    goal_id: int | None = None,
) -> dict:
    """Create a new task in the Nova productivity system.

    Args:
        title: The task title (required).
        description: Optional detailed description of what the task involves.
        category: One of: DSA, Machine Learning, Communication, Fitness, Personal.
                  Defaults to Personal.
        priority: One of: high, medium, low. Defaults to medium.
        due_date: Deadline for the task. Format: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS.
        scheduled_time: Specific time slot allocated for the task. Same format as due_date.
        duration: Expected duration in minutes (e.g. 30, 60, 90).
        goal_id: ID of the parent goal this task contributes to.

    Returns:
        Dictionary with 'status' and created 'task' dict, or error message.
    """
    return tools.create_task(
        title=title,
        description=description,
        category=category,
        priority=priority,
        due_date=due_date,
        scheduled_time=scheduled_time,
        duration=duration,
        goal_id=goal_id,
    )


@mcp.tool()
def nova_get_schedule(
    horizon: str = "day",
    anchor_date: str | None = None,
) -> dict:
    """Get the task schedule overview grouped by date.

    Args:
        horizon: Time window. One of: day, week, month, year. Defaults to day.
        anchor_date: Reference date to centre the horizon on. Format: YYYY-MM-DD
                     or YYYY-MM-DD HH:MM:SS. Defaults to today if not provided.

    Returns:
        Dictionary with 'status', 'schedule' (dict keyed by date), and 'summary'
        containing total counts and completion stats.
    """
    return tools.get_schedule_overview(horizon=horizon, anchor_date=anchor_date)


@mcp.tool()
def nova_get_recommendations(available_time_minutes: int | None = None) -> dict:
    """Get AI-powered task recommendations ranked by urgency and priority.

    Uses Eisenhower-style scoring: overdue tasks score +100, due today +50,
    high priority +30, goal-linked +10, focus-category preference +15.

    Args:
        available_time_minutes: If provided, only recommend tasks that fit within
                                 this many total minutes. Leave None to get all
                                 top recommendations (up to 5).

    Returns:
        Dictionary with 'status', 'recommendations' list (up to 5 tasks with
        'recommendation_score'), and 'total_allocated_time'.
    """
    return tools.get_recommendations(available_time_minutes=available_time_minutes)


@mcp.tool()
def nova_get_productivity_score(period: str = "week") -> dict:
    """Calculate a 0–100 productivity score for the specified period.

    Scoring factors: task completion rate (50 pts), habit consistency (30 pts),
    scheduling discipline (20 pts).

    Args:
        period: One of: day, week, month, year. Defaults to week.

    Returns:
        Dictionary with 'status', 'score' (int 0–100), 'period', 'breakdown'
        (component scores), and a human-readable 'label'.
    """
    return tools.get_productivity_score(period=period)


# ---------------------------------------------------------------------------
# Goal Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def nova_list_goals() -> dict:
    """List all goals with their current progress percentages.

    Returns:
        Dictionary with 'status' and 'goals' list. Each goal includes
        'progress_percent', 'total_tasks', 'completed_tasks'.
    """
    return tools.list_goals()


@mcp.tool()
def nova_get_goal_progress(goal_id: int) -> dict:
    """Fetch detailed progress metrics for a specific goal.

    Args:
        goal_id: The ID of the goal to inspect.

    Returns:
        Dictionary with 'status', 'goal' details, 'metrics' (completion rate,
        overdue count, etc.), and task lists broken down by status.
    """
    return tools.get_goal_progress(goal_id=goal_id)


# ---------------------------------------------------------------------------
# Coaching & Review Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def nova_get_daily_review(anchor_date: str | None = None) -> dict:
    """Get a personalized daily productivity review and coaching recommendations.

    Combines task progress, habit streaks, notifications, and memory to
    generate an actionable coaching summary for the day.

    Args:
        anchor_date: Date to generate the review for. Format: YYYY-MM-DD or
                     YYYY-MM-DD HH:MM:SS. Defaults to today if not provided.

    Returns:
        Dictionary with 'status', 'productivity_score', 'tasks_summary',
        'habits_summary', 'notifications', 'memories', and
        'personalized_recommendations' list.
    """
    return tools.get_daily_review(anchor_date=anchor_date)


@mcp.tool()
def nova_detect_conflicts() -> dict:
    """Detect scheduling conflicts between overlapping tasks.

    Scans all pending tasks with both a scheduled_time and a duration and
    identifies any that overlap. Also proposes a non-overlapping resolution
    schedule.

    Returns:
        Dictionary with 'has_conflicts' (bool), 'conflicts' list (each entry
        has task_1 and task_2 details), and 'proposed_schedule'.
    """
    return tools.detect_conflicts_and_reorganize()


@mcp.tool()
def nova_get_habit_summary(habit_id: int) -> dict:
    """Get detailed stats for a tracked habit including streak and history.

    Args:
        habit_id: The ID of the habit to summarise.

    Returns:
        Dictionary with 'status', 'habit' details, 'streak_current',
        'streak_best', 'completion_rate', and recent 'logs'.
    """
    return tools.get_habit_summary(habit_id=habit_id)


# ---------------------------------------------------------------------------
# Memory Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def nova_recall_memory(query: str | None = None, limit: int = 5) -> dict:
    """Recall entries from Nova's long-term memory store.

    Args:
        query: Optional keyword filter. If provided, only memories whose content
               contains this string (case-insensitive) are returned.
        limit: Maximum number of memories to return. Defaults to 5.

    Returns:
        Dictionary with 'status' and 'memories' list. Each entry includes
        'memory_type', 'content', 'tags', 'importance', and timestamps.
    """
    return tools.recall_memory(query=query, limit=limit)


# ---------------------------------------------------------------------------
# Entry point — run as an MCP stdio server
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # FastMCP handles CLI args (--help, --transport, etc.) automatically.
    # Default transport is stdio — compatible with ADK's McpToolset.
    mcp.run()
