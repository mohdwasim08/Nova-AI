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

import datetime
import os
import sys

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
from google.genai import types
from mcp import StdioServerParameters

from app.store import SQLiteProductivityStore
from app.tools import (
    auto_reschedule_tasks,
    create_goal,
    create_habit,
    create_reminder,
    create_task,
    delete_task,
    detect_conflicts_and_reorganize,
    generate_notifications,
    get_daily_review,
    get_goal_progress,
    get_habit_summary,
    get_productivity_coach_report,
    get_productivity_review,
    get_productivity_score,
    get_recommendations,
    get_schedule_overview,
    get_weekly_review,
    list_goals,
    list_habits,
    list_memories,
    list_notifications,
    list_tasks,
    log_habit_progress,
    manage_preferences,
    recall_memory,
    remember_context,
    reschedule_missed_tasks,
    update_goal,
    update_task,
)

# Load environment variables from app/.env for local development
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_env_path)

# Use Google AI Studio (no GCP credentials needed for local prototype)
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "False")

store = SQLiteProductivityStore()


async def preload_system_status(callback_context: CallbackContext) -> None:
    """before_agent_callback to fetch the current system status and inject it into instructions."""
    now = datetime.datetime.now()
    now_str = now.isoformat()
    today_str = now.date().isoformat()

    # 1. Get Overdue Tasks
    all_tasks = store.list_tasks(status="pending")
    overdue_list = []
    today_list = []

    for t in all_tasks:
        if t["due_date"]:
            if t["due_date"] < now_str:
                overdue_list.append(
                    f"- ID {t['id']}: '{t['title']}' (Category: {t['category']}, Priority: {t['priority']}, Due: {t['due_date']})"
                )
            elif t["due_date"].startswith(today_str):
                today_list.append(
                    f"- ID {t['id']}: '{t['title']}' (Category: {t['category']}, Priority: {t['priority']}, Due: {t['due_date']})"
                )

    overdue_txt = "\n".join(overdue_list) if overdue_list else "None"
    today_txt = "\n".join(today_list) if today_list else "None"

    # 2. Detect conflicts
    conflict_data = detect_conflicts_and_reorganize()
    conflicts_txt = "None"
    if conflict_data.get("has_conflicts"):
        cf_list = []
        for cf in conflict_data["conflicts"]:
            cf_list.append(
                f"- Task '{cf['task_1']['title']}' overlaps with '{cf['task_2']['title']}'"
            )
        conflicts_txt = "\n".join(cf_list)

    # 3. Next 3 Recommendations
    rec_data = get_recommendations()
    rec_list = []
    for r in rec_data.get("recommendations", [])[:3]:
        rec_list.append(
            f"- ID {r['id']}: '{r['title']}' (Score: {r['recommendation_score']}, Category: {r['category']}, Duration: {r['duration'] or 30}m)"
        )
    recs_txt = "\n".join(rec_list) if rec_list else "None"

    schedule_data = get_schedule_overview(horizon="day", anchor_date=now_str)
    schedule_txt = "None"
    if schedule_data.get("schedule"):
        schedule_parts = []
        for day_key, day_tasks in schedule_data["schedule"].items():
            titles = ", ".join(
                f"{task['title']}@{task['scheduled_time'] or task['due_date']}"
                for task in day_tasks[:4]
            )
            schedule_parts.append(f"- {day_key}: {titles}")
        schedule_txt = "\n".join(schedule_parts) if schedule_parts else "None"

    auto_reschedule = auto_reschedule_tasks(anchor_date=now_str)
    recovery_txt = "None"
    if auto_reschedule.get("rescheduled"):
        recovery_txt = "\n".join(
            f"- {task['title']} -> {task['suggested_time']}"
            for task in auto_reschedule["rescheduled"][:3]
        )

    notifications = generate_notifications(anchor_time=now_str)
    notification_txt = "None"
    if notifications.get("notifications"):
        notification_txt = "\n".join(
            f"- {item['title']}: {item['message']}"
            for item in notifications["notifications"][:3]
        )

    from app.tools import _build_coach_recommendations
    recs = _build_coach_recommendations("day")
    coach_txt = "None"
    if recs:
        coach_txt = "\n".join(f"- {item}" for item in recs[:3])

    memories = recall_memory(limit=3)
    memory_txt = "None"
    if memories.get("memories"):
        memory_txt = "\n".join(
            f"- [{entry['memory_type']}] {entry['content']}"
            for entry in memories["memories"][:3]
        )

    # Build status string
    status_summary = f"""Current Local Time: {now.strftime("%Y-%m-%d %H:%M:%S")}
Overdue Tasks:
{overdue_txt}

Tasks Due Today:
{today_txt}

Today's Schedule:
{schedule_txt}

Scheduling Conflicts:
{conflicts_txt}

Top Recommendations to Work on Next:
{recs_txt}

Suggested Recovery Reschedule:
{recovery_txt}

Active Notifications:
{notification_txt}

Coach Guidance:
{coach_txt}

Relevant Long-Term Memory:
{memory_txt}
"""
    # Inject status into state
    callback_context.state["system_status"] = status_summary


system_instruction = """You are Nova, an autonomous personal productivity assistant, scheduler, and accountability partner.
Your primary objective is to help the user stay organized, achieve their goals, and manage their time effectively.

### Persona:
- Professional, supportive, highly organized, and focused on productivity and accountability.
- Proactive: Do not just wait for commands. Check the Current System Status below, and take initiative. If there are overdue tasks, scheduling conflicts, or immediate deadlines, bring them up proactively at the start of your message and suggest a concrete action plan.

### Rules & Safety Guardrails:
1. Never delete tasks without explicit confirmation. If the user asks to delete a task, first warn them and ask them to confirm. Once they confirm, invoke delete_task with confirmation=True.
2. Never modify completed tasks without explicit confirmation. If modifying a completed task, invoke update_task with confirmation=True.
3. Ask before overwriting or shifting scheduled times for existing tasks.
4. Validate dates and times. Tasks should support both due_date (deadline) and scheduled_time (allocated slot) with duration.
5. Prevent duplicate reminders/tasks. If a task with the same title, category, and due date already exists, notify the user.
6. Restrict all operations to the productivity database. Never attempt to read or modify external system files.

### Current System Status:
{system_status}
"""

# ---------------------------------------------------------------------------
# MCP Toolset — Nova MCP Server (launched via stdio subprocess)
# ---------------------------------------------------------------------------
# The Nova MCP server exposes a curated subset of Nova's tools over the
# Model Context Protocol.  Any MCP-compatible client (Claude Desktop, Cursor,
# VS Code Copilot, etc.) can connect to app/mcp_server.py directly. Here we
# consume our own MCP server from within the ADK agent to demonstrate
# end-to-end MCP integration.
_mcp_server_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")

nova_mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[_mcp_server_script],
            env=dict(os.environ),  # Pass current env (includes GOOGLE_API_KEY, NOVA_DB_FILE, etc.)
        ),
        timeout=30,
    ),
    # Prefix MCP tool names so they are clearly distinguishable in traces
    tool_name_prefix="mcp",
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=system_instruction,
    tools=[
        # Native Python tools — full CRUD operations
        create_task,
        update_task,
        delete_task,
        list_tasks,
        create_goal,
        update_goal,
        list_goals,
        get_goal_progress,
        create_reminder,
        list_notifications,
        generate_notifications,
        create_habit,
        list_habits,
        log_habit_progress,
        get_habit_summary,
        remember_context,
        recall_memory,
        list_memories,
        get_recommendations,
        get_schedule_overview,
        detect_conflicts_and_reorganize,
        reschedule_missed_tasks,
        auto_reschedule_tasks,
        get_productivity_review,
        get_productivity_score,
        get_daily_review,
        get_weekly_review,
        get_productivity_coach_report,
        manage_preferences,
        # MCP toolset — Nova MCP server (11 read/query tools exposed via MCP protocol)
        nova_mcp_toolset,
    ],
    before_agent_callback=preload_system_status,
)

app = App(
    root_agent=root_agent,
    name="app",
)
