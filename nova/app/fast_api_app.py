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
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

import app.tools as tools
from app.agent import root_agent
from app.store import SQLiteProductivityStore as _Store
from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback

# Load .env for local development (must be before ADK setup)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_env_path)

setup_telemetry()
logger = None  # Google Cloud Logging disabled for local prototype

allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

# Artifact bucket for ADK (created by Terraform, passed via env var)
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
session_service_uri = None
artifact_service_uri = f"gs://{logs_bucket_name}" if logs_bucket_name else None

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=artifact_service_uri,
    allow_origins=allow_origins,
    session_service_uri=session_service_uri,
    otel_to_cloud=False,
)
app.title = "nova"
app.description = "API for interacting with the Agent nova"

# Enable CORS for frontend dashboard (port 5173 / 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIST_DIR = Path(AGENT_DIR) / "frontend" / "dist"


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    if logger:
        logger.log_struct(feedback.model_dump(), severity="INFO")
    return {"status": "success"}


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api")
@app.get("/api/")
def api_index() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "nova",
        "message": "Nova API is running.",
        "health": "/healthz",
        "docs": "/docs",
        "endpoints": {
            "tasks": "/api/tasks",
            "goals": "/api/goals",
            "categories": "/api/categories",
            "schedule": "/api/schedule",
            "reminders": "/api/reminders",
            "notifications": "/api/notifications",
            "habits": "/api/habits",
            "memory": "/api/memory",
            "coach": "/api/coach",
            "chat": "/api/chat",
        },
    }


# --- Task REST Endpoints ---


class TaskCreateRequest(BaseModel):
    title: str
    description: str | None = None
    category: str = "Personal"
    priority: str = "medium"
    due_date: str | None = None
    scheduled_time: str | None = None
    duration: int | None = None
    goal_id: int | None = None


class TaskUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: str | None = None
    scheduled_time: str | None = None
    duration: int | None = None
    goal_id: int | None = None
    reminder_time: str | None = None
    confirmation: bool = False


@app.get("/api/tasks")
def list_tasks_api(status: str | None = None, category: str | None = None):
    res = tools.list_tasks(status=status, category=category)
    return res


@app.post("/api/tasks")
def create_task_api(req: TaskCreateRequest):
    res = tools.create_task(
        title=req.title,
        description=req.description,
        category=req.category,
        priority=req.priority,
        due_date=req.due_date,
        scheduled_time=req.scheduled_time,
        duration=req.duration,
        goal_id=req.goal_id,
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.put("/api/tasks/{task_id}")
def update_task_api(task_id: int, req: TaskUpdateRequest):
    res = tools.update_task(
        task_id=task_id,
        title=req.title,
        description=req.description,
        category=req.category,
        status=req.status,
        priority=req.priority,
        due_date=req.due_date,
        scheduled_time=req.scheduled_time,
        duration=req.duration,
        goal_id=req.goal_id,
        reminder_time=req.reminder_time,
        confirmation=req.confirmation,
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.delete("/api/tasks/{task_id}")
def delete_task_api(task_id: int, confirmation: bool = False):
    res = tools.delete_task(task_id=task_id, confirmation=confirmation)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


# --- Goal REST Endpoints ---


class GoalCreateRequest(BaseModel):
    title: str
    description: str | None = None
    category: str | None = None
    target_date: str | None = None


class GoalUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    status: str | None = None
    target_date: str | None = None


@app.get("/api/goals")
def list_goals_api():
    return tools.list_goals()


@app.post("/api/goals")
def create_goal_api(req: GoalCreateRequest):
    res = tools.create_goal(
        title=req.title,
        description=req.description,
        category=req.category,
        target_date=req.target_date,
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.put("/api/goals/{goal_id}")
def update_goal_api(goal_id: int, req: GoalUpdateRequest):
    res = tools.update_goal(
        goal_id=goal_id,
        title=req.title,
        description=req.description,
        category=req.category,
        status=req.status,
        target_date=req.target_date,
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.get("/api/goals/{goal_id}/progress")
def goal_progress_api(goal_id: int):
    res = tools.get_goal_progress(goal_id=goal_id)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


# --- Habit, Reminder, Memory, Notification, and Coaching Endpoints ---


class ReminderCreateRequest(BaseModel):
    task_id: int
    reminder_time: str
    message: str | None = None
    delivery_type: str = "task"


class HabitCreateRequest(BaseModel):
    title: str
    description: str | None = None
    category: str = "Personal"
    frequency: str = "daily"
    target_count: int = 1
    start_date: str | None = None
    reminder_time: str | None = None
    goal_id: int | None = None


class HabitLogRequest(BaseModel):
    log_date: str | None = None
    completed_count: int = 1
    notes: str | None = None


class MemoryCreateRequest(BaseModel):
    content: str
    memory_type: str = "context"
    tags: list[str] | None = None
    related_goal_id: int | None = None
    related_task_id: int | None = None
    importance: int = 3


class NotificationUpdateRequest(BaseModel):
    status: str = "read"


@app.get("/api/reminders")
def reminders_api(task_id: int | None = None, include_sent: bool = False):
    return tools.list_reminders(task_id=task_id, include_sent=include_sent)


@app.post("/api/reminders")
def create_reminder_api(req: ReminderCreateRequest):
    res = tools.create_reminder(
        task_id=req.task_id,
        reminder_time=req.reminder_time,
        message=req.message,
        delivery_type=req.delivery_type,
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.get("/api/habits")
def habits_api(status: str | None = None):
    return tools.list_habits(status=status)


@app.post("/api/habits")
def create_habit_api(req: HabitCreateRequest):
    res = tools.create_habit(
        title=req.title,
        description=req.description,
        category=req.category,
        frequency=req.frequency,
        target_count=req.target_count,
        start_date=req.start_date,
        reminder_time=req.reminder_time,
        goal_id=req.goal_id,
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/habits/{habit_id}/log")
def log_habit_api(habit_id: int, req: HabitLogRequest):
    res = tools.log_habit_progress(
        habit_id=habit_id,
        log_date=req.log_date,
        completed_count=req.completed_count,
        notes=req.notes,
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.get("/api/habits/{habit_id}/summary")
def habit_summary_api(habit_id: int):
    res = tools.get_habit_summary(habit_id)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.get("/api/memory")
def memory_api(memory_type: str | None = None, limit: int = 10, query: str | None = None):
    if query:
        return tools.recall_memory(query=query, limit=limit)
    return tools.list_memories(memory_type=memory_type, limit=limit)


@app.post("/api/memory")
def create_memory_api(req: MemoryCreateRequest):
    res = tools.remember_context(
        content=req.content,
        memory_type=req.memory_type,
        tags=req.tags,
        related_goal_id=req.related_goal_id,
        related_task_id=req.related_task_id,
        importance=req.importance,
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.get("/api/notifications")
def notifications_api(status: str | None = None, limit: int = 20):
    return tools.list_notifications(status=status, limit=limit)


@app.post("/api/notifications/process")
def notifications_process_api(anchor_time: str | None = None, mark_delivered: bool = True):
    return tools.generate_notifications(anchor_time=anchor_time, mark_delivered=mark_delivered)


@app.put("/api/notifications/{notification_id}")
def update_notification_api(notification_id: int, req: NotificationUpdateRequest):
    res = tools.mark_notification(notification_id=notification_id, status=req.status)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.get("/api/coach")
def coach_api(period: str = "day", anchor_date: str | None = None):
    res = tools.get_productivity_coach_report(period=period, anchor_date=anchor_date)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.get("/api/productivity-score")
def productivity_score_api(period: str = "week"):
    res = tools.get_productivity_score(period=period)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


# --- Recommendations, Conflicts & Review Endpoints ---


@app.get("/api/recommendations")
def recommendations_api(available_time: int | None = None):
    return tools.get_recommendations(available_time_minutes=available_time)


@app.get("/api/schedule")
def schedule_api(horizon: str = "day", anchor_date: str | None = None):
    res = tools.get_schedule_overview(horizon=horizon, anchor_date=anchor_date)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.get("/api/conflicts")
def conflicts_api():
    return tools.detect_conflicts_and_reorganize()


@app.post("/api/reschedule")
def reschedule_api(
    reschedule_plans: str | None = None,
    apply_changes: bool = False,
    anchor_date: str | None = None,
):
    res = tools.auto_reschedule_tasks(
        reschedule_plans=reschedule_plans,
        apply_changes=apply_changes,
        anchor_date=anchor_date,
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.get("/api/review")
def review_api(period: str = "week"):
    res = tools.get_productivity_review(period=period)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res


# --- Preferences ---


class PreferenceUpdateRequest(BaseModel):
    key: str
    value: str


@app.get("/api/preferences")
def list_preferences_api():
    return tools.manage_preferences(action="list")


@app.post("/api/preferences")
def set_preference_api(req: PreferenceUpdateRequest):
    return tools.manage_preferences(action="set", key=req.key, value=req.value)


# --- Chat API Endpoint (with Programmatic Runner & Streaming) ---


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"
    user_id: str = "default_user"


session_service = InMemorySessionService()
chat_runner = Runner(
    agent=root_agent,
    app_name="app",
    session_service=session_service,
    auto_create_session=True,
)


@app.post("/api/chat")
async def chat_api(req: ChatRequest):
    response_text = ""

    async for event in chat_runner.run_async(
        user_id=req.user_id,
        session_id=req.session_id,
        new_message=types.Content(
            role="user", parts=[types.Part.from_text(text=req.message)]
        ),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_text += part.text

    return {"response": response_text}


@app.post("/api/chat/stream")
async def chat_stream_api(req: ChatRequest):
    async def event_generator():
        async for event in chat_runner.run_async(
            user_id=req.user_id,
            session_id=req.session_id,
            new_message=types.Content(
                role="user", parts=[types.Part.from_text(text=req.message)]
            ),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        yield f"data: {json.dumps({'text': part.text})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Category CRUD endpoints
# ---------------------------------------------------------------------------

_cat_store = _Store()


class CategoryCreateRequest(BaseModel):
    name: str


class CategoryRenameRequest(BaseModel):
    name: str


@app.get("/api/categories")
def list_categories_api():
    cats = _cat_store.list_categories()
    return {"status": "success", "categories": cats}


@app.post("/api/categories")
def create_category_api(req: CategoryCreateRequest):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Category name cannot be empty.")
    cat = _cat_store.create_category(name)
    return {"status": "success", "category": cat}


@app.put("/api/categories/{category_id}")
def rename_category_api(category_id: int, req: CategoryRenameRequest):
    new_name = req.name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Category name cannot be empty.")
    updated = _cat_store.rename_category(category_id, new_name)
    if updated is None:
        raise HTTPException(status_code=404, detail="Category not found.")
    return {"status": "success", "category": updated}


@app.delete("/api/categories/{category_id}")
def delete_category_api(category_id: int):
    result = _cat_store.delete_category(category_id)
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail=result.get("reason", "Not found."))
    return {"status": "success"}


if FRONTEND_DIST_DIR.exists():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def serve_frontend_index():
        return FileResponse(FRONTEND_DIST_DIR / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend_app(full_path: str):
        if full_path.startswith(("api/", "apps/", "run_sse", "feedback", "docs", "openapi.json")):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = FRONTEND_DIST_DIR / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST_DIR / "index.html")


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
