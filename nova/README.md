# Nova — AI Personal Productivity Assistant

An autonomous personal productivity assistant, scheduler, and accountability partner powered by Google ADK 2.x and MCP (Model Context Protocol).

Built with [`agents-cli`](https://github.com/google/agents-cli) version `0.5.0`.

---

## Project Structure

```
nova/
├── app/                           # Core backend agent code
│   ├── __init__.py                # Exports FastAPI app for ADK discovery
│   ├── agent.py                   # ADK Agent + before_agent_callback + MCP integration
│   ├── fast_api_app.py            # FastAPI server (REST API + ADK web UI)
│   ├── mcp_server.py              # Nova MCP Server (FastMCP, stdio transport)
│   ├── tools.py                   # 28 agent tools (tasks, goals, habits, memory, coaching…)
│   ├── store.py                   # SQLiteProductivityStore (DB abstraction layer)
│   ├── database.py                # SQLite schema initialisation (8 tables)
│   ├── app_utils/
│   │   ├── telemetry.py           # OpenTelemetry / GCS log upload setup
│   │   └── typing.py              # Pydantic models (Feedback, etc.)
│   └── .env                       # Local environment variables (GOOGLE_API_KEY, etc.)
├── frontend/                      # React + Vite dashboard
│   └── src/
│       ├── App.jsx                # Full SPA: Dashboard, Calendar, Tasks, Goals, Chat, Settings
│       └── App.css                # Dark-themed design system
├── tests/
│   ├── unit/                      # pytest unit tests (tools, API smoke tests)
│   ├── integration/               # Live agent integration tests
│   └── eval/
│       ├── eval_config.yaml       # LLM-as-judge eval metric config
│       └── datasets/
│           └── basic-dataset.json # 12 realistic productivity eval cases
├── Dockerfile                     # Production container (python:3.12-slim + uvicorn)
├── agents-cli-manifest.yaml       # agents-cli project manifest
├── GEMINI.md                      # AI coding agent development guide
└── pyproject.toml                 # Python dependencies (ADK 2.x, MCP, FastAPI…)
```

> 💡 **Tip:** Use [Gemini CLI](https://github.com/google-gemini/gemini-cli) for AI-assisted development — project context is pre-configured in `GEMINI.md`.

---

## Requirements

Before you begin, ensure you have:
- **Python ≥ 3.11**: Required by ADK 2.x
- **uv**: Fast Python package manager — [Install](https://docs.astral.sh/uv/getting-started/installation/) (`uv add <package>` to add packages)
- **agents-cli**: Google Agents CLI — install with `uv tool install google-agents-cli`
- **Node.js ≥ 18**: Required to build the React frontend (`npm` / `npx`)
- **Google API Key**: Set `GOOGLE_API_KEY` in `app/.env` (get one at [aistudio.google.com](https://aistudio.google.com))

---

## Quick Start

### 1. Install dependencies

```bash
# Install agents-cli and ADK tools (one-time)
uvx google-agents-cli setup

# Install Python backend dependencies
cd nova/
agents-cli install
# or: uv sync
```

### 2. Configure API key

Edit `app/.env`:
```env
GOOGLE_API_KEY=your_api_key_here
GOOGLE_GENAI_USE_VERTEXAI=False
```

### 3. Run the backend

```bash
# Starts FastAPI + ADK web UI on http://localhost:8000
agents-cli playground
# or: uv run uvicorn app.fast_api_app:app --reload --port 8000
```

### 4. Run the frontend (optional — separate terminal)

```bash
cd frontend/
npm install
npm run dev
# Opens http://localhost:5173
```

---

## MCP Server Setup

Nova includes a built-in **MCP (Model Context Protocol) server** (`app/mcp_server.py`) that exposes 11 productivity tools over the stdio transport. It is automatically launched by the ADK agent at runtime. You can also connect to it manually from MCP-compatible clients.

### Run the MCP server standalone

```bash
# Start Nova MCP server on stdio (for MCP client inspection)
uv run python -m app.mcp_server
```

### Connect from Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nova": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/nova", "python", "-m", "app.mcp_server"],
      "env": {
        "GOOGLE_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

### Available MCP Tools

| MCP Tool | Description |
|---|---|
| `mcp_nova_list_tasks` | List tasks with optional status/category filters |
| `mcp_nova_create_task` | Create a new task |
| `mcp_nova_get_schedule` | Get schedule overview (day/week/month/year) |
| `mcp_nova_get_recommendations` | Get AI-ranked task recommendations |
| `mcp_nova_get_productivity_score` | Get 0–100 productivity score |
| `mcp_nova_list_goals` | List all goals with progress |
| `mcp_nova_get_goal_progress` | Get detailed progress for a specific goal |
| `mcp_nova_get_daily_review` | Get personalized coaching report |
| `mcp_nova_detect_conflicts` | Find scheduling conflicts |
| `mcp_nova_get_habit_summary` | Get habit stats and streak info |
| `mcp_nova_recall_memory` | Query long-term memory store |

---

## Commands

| Command | Description |
|---|---|
| `agents-cli install` | Install Python dependencies with uv |
| `agents-cli playground` | Launch local development environment (port 8000) |
| `agents-cli lint` | Run code quality checks (ruff, codespell) |
| `agents-cli eval run` | Run full eval pipeline (generate + grade) |
| `agents-cli eval generate` | Run agent over eval dataset, write traces |
| `agents-cli eval grade` | Score traces and generate HTML report |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests |
| `uv run python -m app.mcp_server` | Start Nova MCP server standalone (stdio) |

---

## Evaluation

The project includes 12 realistic eval cases in `tests/eval/datasets/basic-dataset.json` covering:

- Agent greeting and capability discovery
- Task creation with scheduling and priority
- Listing and filtering tasks
- Goal creation and progress tracking
- Schedule overview (weekly view)
- Smart recommendations with time constraints
- Habit creation
- Productivity score breakdown
- Conflict detection and resolution
- Daily coaching review
- Long-term memory storage
- Safety guardrail validation (delete confirmation)

```bash
# Run the full eval pipeline
agents-cli eval run

# View results in browser
open artifacts/grade_results/results_*.html
```

---

## 🛠️ Project Management

| Command | What It Does |
|---|---|
| `agents-cli scaffold enhance` | Add CI/CD pipelines and Terraform infrastructure |
| `agents-cli infra cicd` | One-command setup of entire CI/CD pipeline + infrastructure |
| `agents-cli scaffold upgrade` | Auto-upgrade to latest version while preserving customisations |

---

## Deployment

```bash
gcloud config set project <your-project-id>
agents-cli deploy
```

To add CI/CD and Terraform, run `agents-cli scaffold enhance`.
To set up production infrastructure, run `agents-cli infra cicd`.

---

## Observability

Built-in telemetry exports to Cloud Trace, BigQuery, and Cloud Logging when `LOGS_BUCKET_NAME` is set.
