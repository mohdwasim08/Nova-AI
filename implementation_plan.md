# Implementation Plan - Autonomous Productivity Assistant "Nova"

This document outlines the design and implementation plan for building **Nova**, an autonomous personal productivity assistant, scheduler, and accountability partner. Nova consists of a Python FastAPI backend powered by the Google Agent Development Kit (ADK) and a modern React/Vite frontend dashboard.

---

## User Review Required

> [!IMPORTANT]
> - **Web Interface Architecture**: The frontend will be a single-page React/Vite application. It will communicate with a FastAPI backend. During local development, the backend will run on port `8000` (serving ADK agent endpoints) and the frontend on port `5173`. We can also configure FastAPI to serve the compiled frontend static files to make it a single deployable unit.
> - **Proactive Pre-load Callback & Chat Integration**: Every time a user opens the chat or sends a message, a `before_agent_callback` queries the database and injects the current date/time, overdue tasks, scheduling conflicts, and goal progress directly into Nova's system context. This allows Nova to proactively warn the user or recommend reschedules.
> - **Safety Confirmations**:
>   - Deleting a task or modifying a completed task requires the model to invoke the tool, which will return a status indicating "confirmation required" unless the user has explicitly confirmed it in the chat context or UI.
>   - Tools will perform input validation on all dates/times (ISO 8601 formatting) and verify that system directories/files are never touched.

## Progress Snapshot

- `Completed`: SQLite schema, task/goal CRUD, safety confirmations, goal progress tracking, proactive agent preload context, chat endpoints, and the core React dashboard shell.
- `Completed`: Planning intelligence phase with schedule-overview APIs for day/week/month/year, automatic missed-task rescheduling around working hours, stronger review metrics, focus-category personalization, and deterministic local unit tests.
- `Completed`: Reminder system, notification engine, habit tracking, long-term memory, and the AI productivity coach layer with daily review, weekly review, productivity scoring, and personalized recommendations.
- `Completed`: Deployment hardening for the existing architecture, including deploy-safe frontend API routing, FastAPI static frontend serving, single-container packaging support, and the missing task/goal edit flows promised by the UI plan.
- `Completed`: Dashboard, calendar, task views, settings, and AI chat are now consistently integrated with the coaching stack, edit flows, notification handling, and deployment-safe API behavior.
- `Completed`: API smoke-check coverage for the bare `/api` entrypoint, preventing callback and deployment checks from failing with a `404 Not Found`.
- `Completed`: Verification and release-prep artifacts, including passing backend/frontend checks plus deployment and summary documentation.
- `Pending`: Advanced proactive assistance loops, background delivery channels beyond local notifications, and additional production hardening.

---

## Proposed Changes

We will create a unified project directory structure:
```
my-first-project/
└── nova/
    ├── app/                     # Backend Python App
    │   ├── __init__.py          # FastAPI App and ADK App setup
    │   ├── agent.py             # Agent definition & callbacks
    │   ├── tools.py             # Agent tools
    │   ├── store.py             # Abstract & SQLite database logic
    │   ├── database.py          # SQLite database schema
    │   └── .env                 # Environment variables
    ├── frontend/                # React/Vite Web Interface
    │   ├── src/                 # React components (Dashboard, Chat, Calendar, Tasks, Goals, Settings)
    │   ├── package.json
    │   └── vite.config.js
    └── pyproject.toml           # Backend dependencies
```

### 1. Database Schema (`nova/app/database.py`)
We will initialize an SQLite database `nova.db` with the following tables:
* **`goals`**: `id` (INTEGER PK), `title` (TEXT), `description` (TEXT), `category` (TEXT), `status` (TEXT: 'ongoing', 'completed', 'abandoned'), `target_date` (TEXT)
* **`tasks`**: `id` (INTEGER PK), `title` (TEXT), `description` (TEXT), `category` (TEXT), `status` (TEXT: 'pending', 'completed', 'missed'), `priority` (TEXT: 'high', 'medium', 'low'), `due_date` (TEXT), `scheduled_time` (TEXT), `duration` (INTEGER), `completed_at` (TEXT), `goal_id` (INTEGER FK)
* **`reminders`**: `id` (INTEGER PK), `task_id` (INTEGER FK), `reminder_time` (TEXT), `is_sent` (INTEGER: 0 or 1)
* **`preferences`**: `key` (TEXT PK), `value` (TEXT JSON)
* **`productivity_logs`**: `date` (TEXT PK), `log_data` (TEXT JSON)

### 2. Backend API & ADK Agent Setup (`nova/app/`)
* **`store.py`**: Define `SQLiteProductivityStore` to perform database CRUD operations.
* **`tools.py`**: Expose agent tools:
  * `create_task`, `update_task` (validates date inputs, blocks editing completed tasks without confirmation), `delete_task` (blocks deleting without confirmation), `list_tasks`.
  * `create_goal`, `update_goal`, `list_goals`, `get_goal_progress`.
  * `get_recommendations` (scores tasks using Eisenhower priority, deadlines, and available duration).
  * `detect_conflicts_and_reorganize` (detects overlapping `scheduled_time` slots and proposes non-overlapping shifts).
  * `reschedule_missed_tasks` (helps shift past-due pending tasks).
  * `manage_preferences` (get/set working hours, target categories).
* **`agent.py`**:
  * Define `root_agent` with professional, supportive, and organized persona.
  * Implement `before_agent_callback` to inject `{system_status}` (current time, list of overdue tasks, conflicts, and next recommendations) into the instructions.
* **`__init__.py`**: Expose a FastAPI app wrapping the ADK runner, with extra REST endpoints for the frontend to query tasks/goals directly (allowing the dashboard to render them visually).

### 3. Frontend Web Interface (`nova/frontend/`)
We will build a React app with a beautiful dark-themed dashboard:
* **Dashboard Tab**: High-level summaries, progress rings for goals, daily checklist, and alert banners for conflicts or overdue tasks.
* **Calendar Tab**: Calendar interface showing tasks scheduled in time slots.
* **Tasks Tab**: Organized list filterable by category (DSA, Machine Learning, Communication, Fitness, Personal, Custom) and priority, with modals to add, update, delete, or reschedule.
* **Goals Tab**: Visual goal tracking displaying target dates, descriptions, and task completion percentages.
* **AI Chat Tab**: Interactive conversational sidebar to speak with Nova, which supports streaming responses.
* **Settings Tab**: Configure working hours, notifications, and focus areas.

---

## Verification Plan

### Automated Verification
* Run `agents-cli lint` to verify backend code quality.
* Run backend tests and execute mock queries.

### Manual Verification
* Run Vite and FastAPI locally.
* Open the browser at `http://localhost:5173/` and test:
  1. Creating a goal and tasks.
  2. Inducing a schedule conflict (e.g. scheduling two tasks for the same hour) and checking if Nova warns you in the dashboard and chat.
  3. Asking Nova "What should I do today?" in the chat panel.
  4. Marking tasks as completed and reviewing the progress metrics.
