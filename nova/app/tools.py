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
import json
from typing import Any

from app.database import get_db_connection
from app.store import SQLiteProductivityStore

store = SQLiteProductivityStore()

# Category definition helper
# Category validation: only reject empty strings; any non-empty name is accepted
VALID_PRIORITIES = {"high", "medium", "low"}
VALID_TASK_STATUSES = {"pending", "completed", "missed"}
VALID_GOAL_STATUSES = {"ongoing", "completed", "abandoned"}
VALID_HABIT_FREQUENCIES = {"daily", "weekly", "monthly"}
VALID_HABIT_STATUSES = {"active", "paused", "completed"}
VALID_MEMORY_TYPES = {"preference", "lesson", "context", "achievement", "obstacle"}
VALID_NOTIFICATION_STATUSES = {"pending", "delivered", "read"}


def _now() -> datetime.datetime:
    return datetime.datetime.now().replace(second=0, microsecond=0)


def _parse_datetime(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    return datetime.datetime.fromisoformat(validate_date(value))


def _parse_date(value: str | None) -> datetime.date | None:
    dt = _parse_datetime(value)
    return dt.date() if dt else None


def _round_up_to_slot(
    dt: datetime.datetime, slot_minutes: int = 30
) -> datetime.datetime:
    remainder = dt.minute % slot_minutes
    if remainder == 0:
        return dt.replace(second=0, microsecond=0)
    return (dt + datetime.timedelta(minutes=slot_minutes - remainder)).replace(
        second=0, microsecond=0
    )


def _get_working_hours() -> tuple[datetime.time, datetime.time]:
    start = store.get_preference("work_start", "09:00")
    end = store.get_preference("work_end", "18:00")
    try:
        start_time = datetime.time.fromisoformat(start)
        end_time = datetime.time.fromisoformat(end)
    except ValueError:
        start_time = datetime.time(hour=9)
        end_time = datetime.time(hour=18)
    return start_time, end_time


def _get_focus_categories() -> set[str]:
    focus = store.get_preference("focus_categories", [])
    if isinstance(focus, list):
        return {str(item) for item in focus}
    return set()


def _build_category_completion_history() -> dict[str, int]:
    tasks = store.list_tasks(status="completed")
    history: dict[str, int] = {}
    for task in tasks:
        category = task["category"] or "Personal"
        history[category] = history.get(category, 0) + 1
    return history


def _get_tasks_for_horizon(
    horizon: str, anchor_date: str | None = None
) -> tuple[datetime.datetime, datetime.datetime]:
    base = _parse_datetime(anchor_date) or _now()
    base = base.replace(hour=0, minute=0, second=0, microsecond=0)
    if horizon == "day":
        return base, base + datetime.timedelta(days=1)
    if horizon == "week":
        start = base - datetime.timedelta(days=base.weekday())
        return start, start + datetime.timedelta(days=7)
    if horizon == "month":
        start = base.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end
    if horizon == "year":
        start = base.replace(month=1, day=1)
        return start, start.replace(year=start.year + 1)
    raise ValueError("Invalid horizon. Use 'day', 'week', 'month', or 'year'.")


def _find_next_available_slot(
    start_at: datetime.datetime,
    duration_minutes: int,
    busy_slots: list[tuple[datetime.datetime, datetime.datetime]],
) -> datetime.datetime:
    work_start, work_end = _get_working_hours()
    cursor = _round_up_to_slot(start_at)

    while True:
        day_start = datetime.datetime.combine(cursor.date(), work_start)
        day_end = datetime.datetime.combine(cursor.date(), work_end)

        if cursor < day_start:
            cursor = day_start

        proposed_end = cursor + datetime.timedelta(minutes=duration_minutes)
        if proposed_end > day_end:
            cursor = datetime.datetime.combine(
                cursor.date() + datetime.timedelta(days=1), work_start
            )
            continue

        overlaps = False
        for busy_start, busy_end in busy_slots:
            if cursor < busy_end and proposed_end > busy_start:
                cursor = _round_up_to_slot(busy_end)
                overlaps = True
                break

        if not overlaps:
            return cursor


def _serialize_task(task: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(task)
    if extra:
        payload.update(extra)
    return payload


def _coerce_tags(tags: str | list[str] | None) -> list[str]:
    if not tags:
        return []
    if isinstance(tags, list):
        return [str(tag).strip() for tag in tags if str(tag).strip()]
    return [tag.strip() for tag in str(tags).split(",") if tag.strip()]


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def validate_date(date_str: str | None) -> str | None:
    """Validates date string format. Supported: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD HH:MM:SS.
    Returns cleaned date string or raises ValueError.
    """
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            return dt.isoformat()
        except ValueError:
            continue
    # Try parsing isoformat directly
    try:
        dt = datetime.datetime.fromisoformat(date_str)
        return dt.isoformat()
    except ValueError:
        raise ValueError(
            f"Invalid date/time format: '{date_str}'. Use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS."
        ) from None


# --- Task Tools ---


def create_task(
    title: str,
    description: str | None = None,
    category: str = "Personal",
    priority: str = "medium",
    due_date: str | None = None,
    scheduled_time: str | None = None,
    duration: int | None = None,
    goal_id: int | None = None,
) -> dict[str, Any]:
    """Creates a new task.

    Args:
        title: The title of the task.
        description: A detailed description of the task.
        category: The category of the task (DSA, Machine Learning, Communication, Fitness, Personal, or custom).
        priority: Task priority (high, medium, low).
        due_date: The deadline for the task (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS).
        scheduled_time: Specific date/time slot to perform the task (YYYY-MM-DD HH:MM:SS).
        duration: Expected duration of the task in minutes.
        goal_id: ID of the parent goal to link to.

    Returns:
        A dict representation of the created task, or an error.
    """
    try:
        clean_due = validate_date(due_date)
        clean_scheduled = validate_date(scheduled_time)
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    # Ensure duplicate reminders/tasks are not made
    existing = store.list_tasks()
    for t in existing:
        if t["title"] == title and t["status"] == "pending":
            if t["due_date"] == clean_due and t["scheduled_time"] == clean_scheduled:
                return {
                    "status": "warning",
                    "message": f"Duplicate pending task '{title}' already exists.",
                    "task": t,
                }

    task = store.create_task(
        title=title,
        description=description,
        category=category,
        priority=priority,
        due_date=clean_due,
        scheduled_time=clean_scheduled,
        duration=duration,
        goal_id=goal_id,
    )
    return {"status": "success", "task": task}


def update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    due_date: str | None = None,
    scheduled_time: str | None = None,
    duration: int | None = None,
    goal_id: int | None = None,
    reminder_time: str | None = None,
    confirmation: bool = False,
) -> dict[str, Any]:
    """Updates an existing task.

    Args:
        task_id: The ID of the task to update.
        title: The updated title.
        description: The updated description.
        category: The updated category.
        status: The updated status (pending, completed, missed).
        priority: The updated priority (high, medium, low).
        due_date: The updated due date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS).
        scheduled_time: The updated scheduled slot (YYYY-MM-DD HH:MM:SS).
        duration: The updated duration in minutes.
        goal_id: The updated parent goal ID.
        reminder_time: The updated reminder time (YYYY-MM-DD HH:MM:SS).
        confirmation: Must be set to True if modifying a task that has already been completed.

    Returns:
        A dict representation of the updated task, or an error/warning message.
    """
    task = store.get_task(task_id)
    if not task:
        return {"status": "error", "message": f"Task with ID {task_id} not found."}

    # Safety Guardrail: Never modify completed tasks without confirmation
    if task["status"] == "completed" and not confirmation:
        return {
            "status": "confirmation_required",
            "message": f"Task '{task['title']}' is already completed. Modifying it requires user confirmation. Please ask the user to confirm, then call update_task again with confirmation=True.",
            "task_id": task_id,
        }

    updates = {}
    if title is not None:
        updates["title"] = title
    if description is not None:
        updates["description"] = description
    if category is not None:
        if category.strip() == "":
            return {"status": "error", "message": "Category cannot be empty."}
        updates["category"] = category
    if priority is not None:
        if priority not in VALID_PRIORITIES:
            return {
                "status": "error",
                "message": "Priority must be one of: high, medium, low.",
            }
        updates["priority"] = priority
    if goal_id is not None:
        updates["goal_id"] = goal_id
    if duration is not None:
        updates["duration"] = duration

    if status is not None:
        if status not in VALID_TASK_STATUSES:
            return {
                "status": "error",
                "message": "Status must be one of: pending, completed, missed.",
            }
        updates["status"] = status
        if status == "completed":
            updates["completed_at"] = datetime.datetime.now().isoformat()
        else:
            updates["completed_at"] = None

    try:
        if due_date is not None:
            updates["due_date"] = validate_date(due_date)
        if scheduled_time is not None:
            updates["scheduled_time"] = validate_date(scheduled_time)
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    # Ask before overwriting important schedules (e.g. if scheduling time changed)
    if (
        scheduled_time is not None
        and task["scheduled_time"]
        and task["scheduled_time"] != updates["scheduled_time"]
        and not confirmation
    ):
        return {
            "status": "confirmation_required",
            "message": f"You are shifting task '{task['title']}' from {task['scheduled_time']} to {updates['scheduled_time']}. Please confirm with the user, then call with confirmation=True.",
            "task_id": task_id,
        }

    if reminder_time is not None:
        try:
            clean_reminder = validate_date(reminder_time) if (reminder_time and reminder_time.strip()) else None
        except ValueError as e:
            return {"status": "error", "message": f"Invalid reminder time: {str(e)}"}
        store.update_task_reminder(task_id, clean_reminder, title or task["title"])

    updated_task = store.update_task(task_id, **updates)
    return {"status": "success", "task": updated_task}


def delete_task(task_id: int, confirmation: bool = False) -> dict[str, Any]:
    """Deletes a task.

    Args:
        task_id: The ID of the task to delete.
        confirmation: Must be set to True. Deleting a task always requires confirmation.

    Returns:
        Success or error dict.
    """
    task = store.get_task(task_id)
    if not task:
        return {"status": "error", "message": f"Task with ID {task_id} not found."}

    # Safety Guardrail: Never delete tasks without confirmation
    if not confirmation:
        return {
            "status": "confirmation_required",
            "message": f"Deleting task '{task['title']}' requires explicit confirmation. Please ask the user to confirm, then call delete_task with confirmation=True.",
            "task_id": task_id,
        }

    deleted = store.delete_task(task_id)
    if deleted:
        return {
            "status": "success",
            "message": f"Task '{task['title']}' deleted successfully.",
        }
    return {"status": "error", "message": "Failed to delete task."}


def list_tasks(
    status: str | None = None, category: str | None = None
) -> dict[str, Any]:
    """Lists all tasks, optionally filtered by status and category.

    Args:
        status: Filter by status (pending, completed, missed).
        category: Filter by category (e.g., DSA, Machine Learning, etc.).

    Returns:
        Dict with status and task list.
    """
    tasks = store.list_tasks(status=status, category=category)
    return {"status": "success", "tasks": tasks}


# --- Goal Tools ---


def create_goal(
    title: str,
    description: str | None = None,
    category: str | None = None,
    target_date: str | None = None,
) -> dict[str, Any]:
    """Creates a new long-term goal.

    Args:
        title: The goal title.
        description: Description of what the goal entails.
        category: Relevant category.
        target_date: Target deadline to achieve this goal (YYYY-MM-DD).

    Returns:
        Dict with created goal.
    """
    try:
        clean_target = validate_date(target_date)
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    goal = store.create_goal(
        title=title,
        description=description,
        category=category,
        target_date=clean_target,
    )
    return {"status": "success", "goal": goal}


def update_goal(
    goal_id: int,
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
    status: str | None = None,
    target_date: str | None = None,
) -> dict[str, Any]:
    """Updates a goal.

    Args:
        goal_id: ID of the goal to update.
        title: New title.
        description: New description.
        category: New category.
        status: Status (ongoing, completed, abandoned).
        target_date: Target achievement date.

    Returns:
        Dict with updated goal.
    """
    goal = store.get_goal(goal_id)
    if not goal:
        return {"status": "error", "message": f"Goal with ID {goal_id} not found."}

    updates = {}
    if title is not None:
        updates["title"] = title
    if description is not None:
        updates["description"] = description
    if category is not None:
        updates["category"] = category
    if status is not None:
        if status not in VALID_GOAL_STATUSES:
            return {
                "status": "error",
                "message": "Status must be one of: ongoing, completed, abandoned.",
            }
        updates["status"] = status

    try:
        if target_date is not None:
            updates["target_date"] = validate_date(target_date)
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    updated = store.update_goal(goal_id, **updates)
    return {"status": "success", "goal": updated}


def list_goals() -> dict[str, Any]:
    """Lists all goals and tracks their progress percentages.

    Returns:
        List of goals with progress.
    """
    goals = store.list_goals()
    all_tasks = store.list_tasks()

    result = []
    for g in goals:
        g_dict = dict(g)
        linked_tasks = [t for t in all_tasks if t["goal_id"] == g["id"]]
        total = len(linked_tasks)
        completed = len([t for t in linked_tasks if t["status"] == "completed"])
        g_dict["progress_percent"] = int((completed / total) * 100) if total > 0 else 0
        g_dict["total_tasks"] = total
        g_dict["completed_tasks"] = completed
        result.append(g_dict)

    return {"status": "success", "goals": result}


def get_goal_progress(goal_id: int) -> dict[str, Any]:
    """Fetches details and detailed progress metrics of a goal.

    Args:
        goal_id: ID of the goal.

    Returns:
        Metrics including completion rate, list of pending tasks, and overdue tasks.
    """
    goal = store.get_goal(goal_id)
    if not goal:
        return {"status": "error", "message": f"Goal with ID {goal_id} not found."}

    all_tasks = store.list_tasks()
    linked_tasks = [t for t in all_tasks if t["goal_id"] == goal_id]
    total = len(linked_tasks)
    completed = [t for t in linked_tasks if t["status"] == "completed"]
    pending = [t for t in linked_tasks if t["status"] == "pending"]
    missed = [t for t in linked_tasks if t["status"] == "missed"]

    # Detect overdue
    now_str = datetime.datetime.now().isoformat()
    overdue = []
    for t in pending:
        if t["due_date"] and t["due_date"] < now_str:
            overdue.append(t)

    progress = int((len(completed) / total) * 100) if total > 0 else 0

    return {
        "status": "success",
        "goal": goal,
        "metrics": {
            "progress_percent": progress,
            "total_tasks": total,
            "completed_count": len(completed),
            "pending_count": len(pending),
            "missed_count": len(missed),
            "overdue_count": len(overdue),
        },
        "tasks": {"completed": completed, "pending": pending, "overdue": overdue},
    }


# --- Productivity, Conflict, & Recommendation Tools ---


def get_recommendations(available_time_minutes: int | None = None) -> dict[str, Any]:
    """Recommends what to work on next using Eisenhower scoring.
    Priority points:
      - Overdue task: +100
      - Due today: +50
      - High priority: +30, Medium: +15, Low: +5
      - Goal-associated: +10

    Args:
        available_time_minutes: Recommend tasks that fit within this limit.

    Returns:
        Recommended task list.
    """
    tasks = store.list_tasks(status="pending")
    now = datetime.datetime.now()
    now_str = now.isoformat()
    today_str = now.date().isoformat()
    focus_categories = _get_focus_categories()
    completion_history = _build_category_completion_history()

    scored_tasks = []
    for t in tasks:
        score = 0

        # Overdue check
        if t["due_date"]:
            if t["due_date"] < now_str:
                score += 100
            elif t["due_date"].startswith(today_str):
                score += 50
            else:
                due_dt = datetime.datetime.fromisoformat(t["due_date"])
                if due_dt <= now + datetime.timedelta(days=7):
                    score += 20

        # Priority scoring
        p = t["priority"].lower()
        if p == "high":
            score += 30
        elif p == "medium":
            score += 15
        else:
            score += 5

        # Goal association
        if t["goal_id"]:
            score += 10

        if t["category"] in focus_categories:
            score += 15

        score += min(completion_history.get(t["category"], 0), 5) * 2

        if t["scheduled_time"]:
            scheduled_dt = datetime.datetime.fromisoformat(t["scheduled_time"])
            if scheduled_dt <= now + datetime.timedelta(hours=24):
                score += 25

        scored_tasks.append((score, t))

    # Sort descending
    scored_tasks.sort(key=lambda x: x[0], reverse=True)

    recommendations = []
    allocated_time = 0

    for score, t in scored_tasks:
        duration = t["duration"] or 30  # Default 30 min
        if available_time_minutes is not None:
            if allocated_time + duration <= available_time_minutes:
                t_copy = dict(t)
                t_copy["recommendation_score"] = score
                recommendations.append(t_copy)
                allocated_time += duration
        else:
            t_copy = dict(t)
            t_copy["recommendation_score"] = score
            recommendations.append(t_copy)

    return {
        "status": "success",
        "recommendations": recommendations[:5],
        "total_allocated_time": allocated_time,
    }


def detect_conflicts_and_reorganize() -> dict[str, Any]:
    """Scans pending tasks to detect overlapping scheduled times. Proposes resolution schedule.

    Returns:
        List of conflicts and a proposed non-overlapping schedule.
    """
    tasks = store.list_tasks(status="pending")
    scheduled_tasks = [t for t in tasks if t["scheduled_time"] and t["duration"]]

    # Sort by scheduled time
    scheduled_tasks.sort(key=lambda x: x["scheduled_time"])

    conflicts = []
    proposed_schedule = []

    for i in range(len(scheduled_tasks)):
        t1 = scheduled_tasks[i]
        t1_start = datetime.datetime.fromisoformat(t1["scheduled_time"])
        t1_end = t1_start + datetime.timedelta(minutes=t1["duration"])

        # Compare with subsequent tasks
        for j in range(i + 1, len(scheduled_tasks)):
            t2 = scheduled_tasks[j]
            t2_start = datetime.datetime.fromisoformat(t2["scheduled_time"])
            if t2_start < t1_end:
                # Overlap!
                conflicts.append(
                    {
                        "task_1": {
                            "id": t1["id"],
                            "title": t1["title"],
                            "slot": f"{t1['scheduled_time']} ({t1['duration']}m)",
                        },
                        "task_2": {
                            "id": t2["id"],
                            "title": t2["title"],
                            "slot": f"{t2['scheduled_time']} ({t2['duration']}m)",
                        },
                    }
                )

    # Build proposed reorganization if conflicts exist
    if conflicts:
        # Simplistic resolver: Push overlapping tasks to start right after previous ends
        curr_time = None
        for t in scheduled_tasks:
            t_start = datetime.datetime.fromisoformat(t["scheduled_time"])
            if curr_time is None or t_start >= curr_time:
                proposed_schedule.append(
                    {
                        "id": t["id"],
                        "title": t["title"],
                        "original_time": t["scheduled_time"],
                        "new_time": t["scheduled_time"],
                    }
                )
                curr_time = t_start + datetime.timedelta(minutes=t["duration"])
            else:
                new_start_str = curr_time.isoformat()
                proposed_schedule.append(
                    {
                        "id": t["id"],
                        "title": t["title"],
                        "original_time": t["scheduled_time"],
                        "new_time": new_start_str,
                    }
                )
                curr_time = curr_time + datetime.timedelta(minutes=t["duration"])

    return {
        "status": "success",
        "has_conflicts": len(conflicts) > 0,
        "conflicts": conflicts,
        "proposed_schedule": proposed_schedule,
    }


def reschedule_missed_tasks(reschedule_plans: str) -> dict[str, Any]:
    """Bulk reschedules tasks based on the provided JSON plan.

    Args:
        reschedule_plans: A JSON string mapping Task IDs to new ISO scheduled times.
                          Example: '{"1": "2026-07-02T10:00:00", "5": "2026-07-02T14:30:00"}'

    Returns:
        Status update list.
    """
    return auto_reschedule_tasks(reschedule_plans=reschedule_plans, apply_changes=True)


def auto_reschedule_tasks(
    reschedule_plans: str | None = None,
    apply_changes: bool = False,
    anchor_date: str | None = None,
) -> dict[str, Any]:
    """Reschedules missed or overdue tasks automatically around working hours.

    Args:
        reschedule_plans: Optional JSON map of task IDs to explicit schedule times.
        apply_changes: Persist the calculated schedule back into the database.
        anchor_date: Optional ISO timestamp used as the rescheduling baseline.

    Returns:
        Proposed or applied reschedule plan.
    """
    if reschedule_plans:
        try:
            plans = json.loads(reschedule_plans)
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to parse reschedule plans JSON: {e}",
            }

        rescheduled = []
        errors = []
        for task_id_str, new_time in plans.items():
            try:
                tid = int(task_id_str)
                clean_time = validate_date(new_time)
                updated = store.update_task(
                    tid, scheduled_time=clean_time, status="pending"
                )
                if updated:
                    rescheduled.append(updated)
                else:
                    errors.append(f"Task {tid} not found.")
            except Exception as e:
                errors.append(f"Failed to update task {task_id_str}: {e}")

        return {
            "status": "success",
            "mode": "manual",
            "rescheduled_count": len(rescheduled),
            "rescheduled": rescheduled,
            "errors": errors,
        }

    now = _parse_datetime(anchor_date) or _now()
    pending_tasks = store.list_tasks()
    candidates = []
    busy_slots: list[tuple[datetime.datetime, datetime.datetime]] = []

    for task in pending_tasks:
        if (
            task["status"] == "pending"
            and task["scheduled_time"]
            and task["duration"]
            and datetime.datetime.fromisoformat(task["scheduled_time"]) >= now
        ):
            start = datetime.datetime.fromisoformat(task["scheduled_time"])
            busy_slots.append((start, start + datetime.timedelta(minutes=task["duration"])))

        is_overdue = task["status"] == "pending" and task["due_date"] and task["due_date"] < now.isoformat()
        if task["status"] == "missed" or is_overdue:
            candidates.append(task)

    candidates.sort(
        key=lambda task: (
            task["priority"] != "high",
            _parse_datetime(task["due_date"]) or now + datetime.timedelta(days=365),
            task["id"],
        )
    )

    proposals = []
    for task in candidates:
        duration = task["duration"] or 30
        slot = _find_next_available_slot(now, duration, sorted(busy_slots))
        slot_end = slot + datetime.timedelta(minutes=duration)
        busy_slots.append((slot, slot_end))

        proposal = _serialize_task(
            task,
            {
                "previous_status": task["status"],
                "previous_scheduled_time": task["scheduled_time"],
                "suggested_time": slot.isoformat(),
            },
        )
        proposals.append(proposal)

        if apply_changes:
            store.update_task(
                task["id"],
                scheduled_time=slot.isoformat(),
                status="pending",
            )

    return {
        "status": "success",
        "mode": "automatic",
        "apply_changes": apply_changes,
        "rescheduled_count": len(proposals),
        "rescheduled": proposals,
    }


def get_schedule_overview(
    horizon: str = "day", anchor_date: str | None = None
) -> dict[str, Any]:
    """Returns a structured schedule for day, week, month, or year horizons."""
    try:
        start, end = _get_tasks_for_horizon(horizon, anchor_date)
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    tasks = store.list_tasks()
    goals = store.list_goals()
    start_iso = start.isoformat()
    end_iso = end.isoformat()
    buckets: dict[str, list[dict[str, Any]]] = {}
    overdue = []
    unscheduled = []

    for task in tasks:
        scheduled = _parse_datetime(task["scheduled_time"])
        due = _parse_datetime(task["due_date"])
        if task["status"] == "pending" and due and due < start:
            overdue.append(task)
        if task["status"] == "pending" and not scheduled:
            unscheduled.append(task)
        if scheduled and start_iso <= scheduled.isoformat() < end_iso:
            bucket_key = scheduled.date().isoformat()
            buckets.setdefault(bucket_key, []).append(task)
        elif due and not scheduled and start_iso <= due.isoformat() < end_iso:
            bucket_key = due.date().isoformat()
            buckets.setdefault(bucket_key, []).append(task)

    for bucket_tasks in buckets.values():
        bucket_tasks.sort(
            key=lambda task: (
                task["scheduled_time"] or task["due_date"] or "",
                task["priority"],
                task["id"],
            )
        )

    goal_deadlines = []
    for goal in goals:
        target_date = _parse_datetime(goal["target_date"])
        if target_date and start_iso <= target_date.isoformat() < end_iso:
            goal_deadlines.append(goal)

    return {
        "status": "success",
        "horizon": horizon,
        "anchor": start_iso,
        "range_end": end_iso,
        "schedule": buckets,
        "goal_deadlines": goal_deadlines,
        "overdue_tasks": overdue,
        "unscheduled_tasks": unscheduled,
        "summary": {
            "scheduled_task_count": sum(len(tasks) for tasks in buckets.values()),
            "overdue_count": len(overdue),
            "unscheduled_count": len(unscheduled),
            "goal_deadline_count": len(goal_deadlines),
        },
    }


# --- Reminders, Notifications, Habits, Memory, and Coaching ---


def create_reminder(
    task_id: int,
    reminder_time: str,
    message: str | None = None,
    delivery_type: str = "task",
) -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task:
        return {"status": "error", "message": f"Task with ID {task_id} not found."}
    try:
        clean_time = validate_date(reminder_time)
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    reminder = store.create_reminder_entry(
        task_id=task_id,
        reminder_time=clean_time,
        message=message or f"Reminder: {task['title']}",
        delivery_type=delivery_type,
    )
    return {"status": "success", "reminder": reminder}


def list_reminders(
    task_id: int | None = None, include_sent: bool = False
) -> dict[str, Any]:
    reminders = store.list_reminders(task_id=task_id, only_pending=not include_sent)
    return {"status": "success", "reminders": reminders}


def create_habit(
    title: str,
    description: str | None = None,
    category: str = "Personal",
    frequency: str = "daily",
    target_count: int = 1,
    start_date: str | None = None,
    reminder_time: str | None = None,
    goal_id: int | None = None,
) -> dict[str, Any]:
    if frequency not in VALID_HABIT_FREQUENCIES:
        return {
            "status": "error",
            "message": "Frequency must be one of: daily, weekly, monthly.",
        }
    try:
        clean_start = validate_date(start_date) if start_date else _now().date().isoformat()
        clean_reminder = validate_date(reminder_time) if reminder_time else None
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    habit = store.create_habit(
        title=title,
        description=description,
        category=category,
        frequency=frequency,
        target_count=max(1, target_count),
        start_date=clean_start,
        reminder_time=clean_reminder,
        goal_id=goal_id,
    )
    return {"status": "success", "habit": habit}


def list_habits(status: str | None = None) -> dict[str, Any]:
    habits = store.list_habits(status=status)
    summaries = []
    for habit in habits:
        summary = get_habit_summary(habit["id"])
        summaries.append(summary["habit"] if summary["status"] == "success" else habit)
    return {"status": "success", "habits": summaries}


def log_habit_progress(
    habit_id: int,
    log_date: str | None = None,
    completed_count: int = 1,
    notes: str | None = None,
) -> dict[str, Any]:
    habit = store.get_habit(habit_id)
    if not habit:
        return {"status": "error", "message": f"Habit with ID {habit_id} not found."}
    try:
        clean_date = validate_date(log_date) if log_date else _now().date().isoformat()
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    log = store.create_habit_log(
        habit_id=habit_id,
        log_date=clean_date,
        completed_count=max(1, completed_count),
        notes=notes,
    )
    summary = _compute_habit_metrics(habit_id)
    store.update_habit(
        habit_id,
        streak_current=summary["streak_current"],
        streak_best=summary["streak_best"],
        last_completed_date=summary["last_completed_date"],
    )
    updated_habit = store.get_habit(habit_id)
    return {"status": "success", "habit": updated_habit, "log": log, "summary": summary}


def _compute_habit_metrics(habit_id: int) -> dict[str, Any]:
    habit = store.get_habit(habit_id)
    if not habit:
        return {"streak_current": 0, "streak_best": 0, "completion_rate": 0, "last_completed_date": None}
    logs = store.list_habit_logs(habit_id=habit_id)
    if not logs:
        return {"streak_current": 0, "streak_best": 0, "completion_rate": 0, "last_completed_date": None}

    target_count = max(1, habit["target_count"])
    frequency = habit["frequency"]
    grouped: dict[str, int] = {}
    for log in logs:
        dt = _parse_datetime(log["log_date"]) or _now()
        if frequency == "weekly":
            key = f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}"
        elif frequency == "monthly":
            key = f"{dt.year}-{dt.month:02d}"
        else:
            key = dt.date().isoformat()
        grouped[key] = grouped.get(key, 0) + (log["completed_count"] or 0)

    qualified = sorted(key for key, count in grouped.items() if count >= target_count)
    streak_best = 0
    streak_current = 0

    if frequency == "daily":
        qualified_dates = sorted(datetime.date.fromisoformat(key) for key in qualified)
        for index, curr in enumerate(qualified_dates):
            current_streak = 1
            pointer = index - 1
            prev = curr
            while pointer >= 0 and (prev - qualified_dates[pointer]).days == 1:
                current_streak += 1
                prev = qualified_dates[pointer]
                pointer -= 1
            streak_best = max(streak_best, current_streak)
        today = _now().date()
        streak_current = 0
        cursor = today
        qualified_set = set(qualified_dates)
        while cursor in qualified_set:
            streak_current += 1
            cursor -= datetime.timedelta(days=1)
        last_completed = qualified_dates[-1].isoformat()
    else:
        streak_best = len(qualified)
        streak_current = 1 if qualified else 0
        last_completed = qualified[-1] if qualified else None

    completion_rate = int((len(qualified) / max(len(grouped), 1)) * 100)
    return {
        "streak_current": streak_current,
        "streak_best": streak_best,
        "completion_rate": completion_rate,
        "last_completed_date": last_completed,
    }


def get_habit_summary(habit_id: int) -> dict[str, Any]:
    habit = store.get_habit(habit_id)
    if not habit:
        return {"status": "error", "message": f"Habit with ID {habit_id} not found."}
    metrics = _compute_habit_metrics(habit_id)
    logs = store.list_habit_logs(habit_id=habit_id, limit=10)
    habit_with_metrics = dict(habit)
    habit_with_metrics.update(metrics)
    habit_with_metrics["recent_logs"] = logs
    return {"status": "success", "habit": habit_with_metrics}


def remember_context(
    content: str,
    memory_type: str = "context",
    tags: str | list[str] | None = None,
    related_goal_id: int | None = None,
    related_task_id: int | None = None,
    importance: int = 3,
) -> dict[str, Any]:
    if memory_type not in VALID_MEMORY_TYPES:
        return {
            "status": "error",
            "message": f"Memory type must be one of: {', '.join(sorted(VALID_MEMORY_TYPES))}.",
        }
    memory = store.create_memory_entry(
        memory_type=memory_type,
        content=content,
        tags=_coerce_tags(tags),
        related_goal_id=related_goal_id,
        related_task_id=related_task_id,
        importance=max(1, min(5, importance)),
        created_at=_now().isoformat(),
    )
    return {"status": "success", "memory": memory}


def recall_memory(query: str | None = None, limit: int = 5) -> dict[str, Any]:
    memories = store.list_memory_entries(limit=50)
    if query:
        needle = query.lower()
        filtered = []
        for memory in memories:
            haystack = " ".join([memory["content"], " ".join(memory.get("tags", []))]).lower()
            if needle in haystack:
                filtered.append(memory)
        memories = filtered
    selected = memories[:limit]
    for memory in selected:
        store.update_memory_entry(memory["id"], last_recalled_at=_now().isoformat())
    return {"status": "success", "memories": selected}


def list_memories(memory_type: str | None = None, limit: int = 10) -> dict[str, Any]:
    return {
        "status": "success",
        "memories": store.list_memory_entries(memory_type=memory_type, limit=limit),
    }


def generate_notifications(
    anchor_time: str | None = None,
    mark_delivered: bool = False,
) -> dict[str, Any]:
    now = _parse_datetime(anchor_time) or _now()
    created = []
    reminders = store.list_reminders(only_pending=True)
    for reminder in reminders:
        reminder_dt = _parse_datetime(reminder["reminder_time"])
        if reminder_dt and reminder_dt <= now:
            # Check if notification already exists to prevent duplicates
            if store.notification_exists("reminder", reminder["id"]):
                if mark_delivered:
                    store.mark_reminder_sent(reminder["id"])
                continue

            task = store.get_task(reminder["task_id"])
            title = f"Reminder for {task['title']}" if task else "Task reminder"
            notification = store.create_notification(
                source_type="reminder",
                source_id=reminder["id"],
                title=title,
                message=reminder["message"] or title,
                severity="info",
                scheduled_for=reminder["reminder_time"],
                status="delivered" if mark_delivered else "pending",
                metadata={"task_id": reminder["task_id"]},
            )
            created.append(notification)
            if mark_delivered:
                store.mark_reminder_sent(reminder["id"])

    for task in store.list_tasks(status="pending"):
        due_dt = _parse_datetime(task["due_date"])
        if due_dt and due_dt < now:
            existing = store.find_notification("task_overdue", task["id"])
            if not existing:
                created.append(
                    store.create_notification(
                        source_type="task_overdue",
                        source_id=task["id"],
                        title="Overdue task",
                        message=f"{task['title']} is overdue. Nova recommends a recovery plan.",
                        severity="warning",
                        scheduled_for=task["due_date"],
                        status="pending",
                        metadata={"category": task["category"]},
                    )
                )

    for goal in store.list_goals():
        target_dt = _parse_datetime(goal["target_date"])
        if target_dt and now <= target_dt <= now + datetime.timedelta(days=3):
            existing = store.find_notification("goal_deadline", goal["id"])
            if not existing:
                created.append(
                    store.create_notification(
                        source_type="goal_deadline",
                        source_id=goal["id"],
                        title="Goal deadline approaching",
                        message=f"{goal['title']} is due soon. Review the remaining work today.",
                        severity="info",
                        scheduled_for=goal["target_date"],
                        status="pending",
                        metadata={"goal_id": goal["id"]},
                    )
                )

    today_key = now.date().isoformat()
    for habit in store.list_habits(status="active"):
        if habit["reminder_time"]:
            reminder_dt = _parse_datetime(habit["reminder_time"])
            recent_logs = store.list_habit_logs(habit_id=habit["id"], limit=20)
            completed_today = any(
                (_parse_datetime(log["log_date"]) or now).date().isoformat() == today_key
                for log in recent_logs
            )
            if reminder_dt and reminder_dt <= now and not completed_today:
                existing = store.find_notification("habit_due", habit["id"])
                if not existing:
                    created.append(
                        store.create_notification(
                            source_type="habit_due",
                            source_id=habit["id"],
                            title="Habit check-in",
                            message=f"It's time for {habit['title']}. Keep your streak alive.",
                            severity="info",
                            scheduled_for=habit["reminder_time"],
                            status="pending",
                            metadata={"habit_id": habit["id"]},
                        )
                    )

    pending = store.list_notifications(status="pending", limit=20)
    return {"status": "success", "created_notifications": created, "notifications": pending}


def list_notifications(status: str | None = None, limit: int = 20) -> dict[str, Any]:
    return {
        "status": "success",
        "notifications": store.list_notifications(status=status, limit=limit),
    }


def mark_notification(
    notification_id: int,
    status: str = "read",
) -> dict[str, Any]:
    if status not in VALID_NOTIFICATION_STATUSES:
        return {"status": "error", "message": "Invalid notification status."}
    delivered_at = _now().isoformat() if status == "delivered" else None
    notification = store.update_notification(
        notification_id, status=status, delivered_at=delivered_at
    )
    if not notification:
        return {
            "status": "error",
            "message": f"Notification with ID {notification_id} not found.",
        }
    return {"status": "success", "notification": notification}


def get_productivity_score(period: str = "week") -> dict[str, Any]:
    review = get_productivity_review(period)
    if review["status"] != "success":
        return review
    habits = store.list_habits(status="active")
    habit_scores = []
    for habit in habits:
        metrics = _compute_habit_metrics(habit["id"])
        habit_scores.append(metrics["completion_rate"])
    habit_score = int(sum(habit_scores) / len(habit_scores)) if habit_scores else 75

    summary = review["summary"]
    score = 55
    score += min(summary["completed_count"] * 6, 25)
    score += min(summary["completion_rate"] // 2, 20)
    score += (habit_score - 50) // 5
    score -= summary["missed_count"] * 8
    score -= summary["overdue_pending_count"] * 5
    return {
        "status": "success",
        "period": period,
        "score": _clamp_score(score),
        "habit_score": habit_score,
        "task_summary": summary,
    }


def _build_coach_recommendations(period: str) -> list[str]:
    recommendations = []
    score_data = get_productivity_score(period)
    review = get_productivity_review(period)
    notifications = store.list_notifications(status="pending", limit=5)
    focus_categories = _get_focus_categories()
    top_rec = get_recommendations().get("recommendations", [])

    if score_data.get("score", 0) < 60:
        recommendations.append("Reduce overload by rescheduling overdue work into smaller focus blocks today.")
    if review["summary"]["overdue_pending_count"] > 0:
        recommendations.append("Clear at least one overdue task first to rebuild momentum.")
    if notifications:
        recommendations.append("Review your pending reminders and notifications so nothing important slips.")
    if focus_categories:
        recommendations.append(
            f"Protect time for your chosen focus areas: {', '.join(sorted(focus_categories))}."
        )
    if top_rec:
        recommendations.append(
            f"Your highest-value next step is '{top_rec[0]['title']}' based on urgency, priority, and context."
        )
    if not recommendations:
        recommendations.append("You're in a stable rhythm. Keep following your current schedule and habit streaks.")
    return recommendations[:5]


def get_productivity_coach_report(
    period: str = "day", anchor_date: str | None = None
) -> dict[str, Any]:
    horizon = "day" if period == "day" else "week"
    review_period = "day" if period == "day" else "week"
    generate_notifications(anchor_time=anchor_date)
    schedule = get_schedule_overview(horizon=horizon, anchor_date=anchor_date)
    review = get_productivity_review(review_period)
    score = get_productivity_score(review_period)
    notifications = list_notifications(status="pending", limit=5)["notifications"]
    memories = recall_memory(limit=3)["memories"]
    habits = list_habits(status="active")["habits"][:5]

    return {
        "status": "success",
        "period": period,
        "productivity_score": score.get("score", 0),
        "review": review,
        "schedule": schedule,
        "notifications": notifications,
        "habits": habits,
        "memories": memories,
        "personalized_recommendations": _build_coach_recommendations(review_period),
    }


def get_daily_review(anchor_date: str | None = None) -> dict[str, Any]:
    return get_productivity_coach_report(period="day", anchor_date=anchor_date)


def get_weekly_review(anchor_date: str | None = None) -> dict[str, Any]:
    return get_productivity_coach_report(period="week", anchor_date=anchor_date)


# --- Productivity Review & Preferences ---


def get_productivity_review(period: str) -> dict[str, Any]:
    """Generates productivity log summary for a 'day', 'week', or 'month'.

    Args:
        period: 'day', 'week', or 'month'.

    Returns:
        Productivity stats like tasks completed vs created, categories breakdown.
    """
    tasks = store.list_tasks()
    now = datetime.datetime.now()

    # Filter based on period
    if period == "day":
        cutoff = now - datetime.timedelta(days=1)
    elif period == "week":
        cutoff = now - datetime.timedelta(weeks=1)
    elif period == "month":
        cutoff = now - datetime.timedelta(days=30)
    elif period == "year":
        cutoff = now - datetime.timedelta(days=365)
    else:
        return {
            "status": "error",
            "message": "Invalid period. Choose 'day', 'week', 'month', or 'year'.",
        }

    cutoff_str = cutoff.isoformat()

    completed_count = 0
    missed_count = 0
    overdue_pending_count = 0
    category_counts = {}
    scheduled_minutes = 0
    completed_minutes = 0

    for t in tasks:
        # Rough check: if tasks are modified/completed after cutoff
        # (Since we don't store created_at, we can rely on due_date/completed_at)
        is_relevant = False
        if t["completed_at"] and t["completed_at"] >= cutoff_str:
            completed_count += 1
            is_relevant = True
        elif t["due_date"] and t["due_date"] >= cutoff_str:
            is_relevant = True

        if t["status"] == "missed" and t["due_date"] and t["due_date"] >= cutoff_str:
            missed_count += 1
        if t["status"] == "pending" and t["due_date"] and t["due_date"] < now.isoformat():
            overdue_pending_count += 1

        if is_relevant:
            cat = t["category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1
            scheduled_minutes += t["duration"] or 0
            if t["status"] == "completed":
                completed_minutes += t["duration"] or 0

    relevant_task_count = sum(category_counts.values())
    completion_rate = int((completed_count / relevant_task_count) * 100) if relevant_task_count else 0
    top_category = max(category_counts, key=category_counts.get) if category_counts else None

    return {
        "status": "success",
        "period": period,
        "summary": {
            "completed_count": completed_count,
            "missed_count": missed_count,
            "overdue_pending_count": overdue_pending_count,
            "active_tasks_in_period": relevant_task_count,
            "category_distribution": category_counts,
            "completion_rate": completion_rate,
            "top_category": top_category,
            "scheduled_minutes": scheduled_minutes,
            "completed_minutes": completed_minutes,
        },
    }


def manage_preferences(
    action: str, key: str | None = None, value: str | None = None
) -> dict[str, Any]:
    """Gets, sets, or lists preferences.

    Args:
        action: 'get', 'set', or 'list'.
        key: Preference key.
        value: JSON string of value to set.

    Returns:
        Result dictionary.
    """
    if action == "get":
        if not key:
            return {"status": "error", "message": "Key is required for 'get'."}
        pref = store.get_preference(key)
        return {"status": "success", "key": key, "value": pref}
    elif action == "set":
        if not key or value is None:
            return {
                "status": "error",
                "message": "Key and value are required for 'set'.",
            }
        try:
            parsed_val = json.loads(value)
        except Exception:
            parsed_val = value  # Set as plain string if JSON decode fails
        store.set_preference(key, parsed_val)
        return {"status": "success", "key": key, "value": parsed_val}
    elif action == "list":
        # SQLite preferences query
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM preferences")
        rows = cursor.fetchall()
        conn.close()
        prefs = {}
        for r in rows:
            try:
                prefs[r["key"]] = json.loads(r["value"])
            except Exception:
                prefs[r["key"]] = r["value"]
        return {"status": "success", "preferences": prefs}
    else:
        return {
            "status": "error",
            "message": "Invalid action. Use 'get', 'set', or 'list'.",
        }
